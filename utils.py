import os
import random
import numpy as np
from tkinter import *
from PIL import ImageTk, Image
from tkinter import filedialog, ttk
from skimage import io, color
from skimage.draw import polygon
from scipy import misc
from segcanvas.canvas import CanvasImage

COLORS = np.array([[0, 0, 0], [255, 0, 0], [0, 255, 0], [0, 0, 255], [0, 255, 255], [255, 0, 255], [255, 255, 0]])
N_REGIONS = 5


class MapImage:
    channels = ['blue', 'green', 'red', 'nir', 'swir1', '06', 'swir2']
    chan_dict = {str(i + 1).zfill(2): c for i, c in enumerate(channels)}

    def __init__(self):
        self.bands = {b: None for b in self.channels}
        self.mask = None
        self.original_image = None
        self.original_array = None
        self.filtered_image = None

    def load_band(self, b, img_path):
        try:
            self.bands[b] = np.array(Image.open(img_path))
        except FileNotFoundError:
            pass

    def load(self, img_path):
        img_name = self._get_img_name(img_path)
        if img_name != '':
            for n, c in self.chan_dict.items():
                self.load_band(c, f'{img_name}_{c}_{n}.tif')

    def create_original_img(self, b):
        arrays = [self.bands[self.chan_dict[c]] for c in b]
        if len(arrays) == 1:
            arrays *= 3
        if len(arrays) == 2:
            arrays += [np.zeros_like(arrays[0])]
        assert len(arrays) == 3
        self.original_image = misc.toimage(np.array(arrays))  # [:, ::-1, :] todo
        # Image.fromarray(np.array(arrays).transpose([1,2,0]), mode='RGB') ???
        self.original_array = np.array(self.original_image)

    def create_filtered_image(self):
        arrays = [self.bands[self.chan_dict[c]] for c in self.mask.channels]

        types = self.mask.get_value(*tuple(arrays))
        filtered_image_array = self.original_array * 0.5 + get_color(types) * 0.5
        self.filtered_image = misc.toimage(filtered_image_array, cmin=0, cmax=255)

    @classmethod
    def _get_img_name(cls, img_path):
        if not img_path.endswith('.tif'):
            return ''
        img_path = img_path[:-4]
        for n, c in cls.chan_dict.items():
            if img_path.endswith(f'_{c}_{n}'):
                return img_path[:-2 - len(c) - len(n)]
        return ''


class _RegionImage:
    def __init__(self, base_image):
        self.base_image = base_image
        self.base_array = np.array(self.base_image)
        self.crafted_array = np.zeros(self.base_array.shape[:2], dtype=int)
        self._create_crafted_image()

    def _create_crafted_image(self):
        crafted_image_array = self.base_array * 0.5 + get_color(self.crafted_array) * 0.5
        self.crafted_image = misc.toimage(crafted_image_array, cmin=0, cmax=255)


class Mask:
    def __init__(self, x_min, x_max, x_step, y_min, y_max, y_step, array, channels):
        self.x_min = x_min
        self.x_max = x_max
        self.x_step = x_step
        self.y_min = y_min
        self.y_max = y_max
        self.y_step = y_step
        self.array = array
        self.channels = channels

        self._vec_get_value()

    def _vec_get_value(self):
        @np.vectorize
        def f(x, y):
            x_ = min(int((x - self.x_min) // self.x_step), self.array.shape[0] - 1)
            y_ = min(int((y - self.y_min) // self.y_step), self.array.shape[1] - 1)
            return self.array[x_][y_]

        self.get_value = f

    def update_array(self, array):
        self.array = array
        self._vec_get_value()


def get_color(t):
    return np.array([COLORS.transpose()[i].take(t) for i in range(3)]).transpose((1, 2, 0))


# def get_default_mask(map_image):
#     b = ['03', '04']
#     arrays = [map_image.bands[map_image.chan_dict[c]] for c in b]
#     params = [[arr.min(), arr.max(), (arr.max() - arr.min()) / 256] for arr in arrays]
#
#     mask_array = np.zeros([256, 256], dtype=int)
#
#     return Mask(*tuple(params[0]), *tuple(params[1]), mask_array, b)


class NamedFrame(ttk.Frame):
    def __init__(self, master, name=None, number=0):
        super().__init__(master)
        self.name = name
        self.number = number
        self.pack()


class RegionImage(CanvasImage):
    def __init__(self, canvas_frame, canvas, region_window):
        super().__init__(canvas_frame, canvas)
        self.canvas.bind('<Button-1>', self.__left_mouse_button_pressed)  # move vertex or subdivide edge
        self.canvas.bind('<Double-Button-1>', self.__left_mouse_double_click)  # todo delete vertex or polygon
        # todo https://codereview.stackexchange.com/questions/198056/on-click-doubleclick-and-mouse-moving
        self.canvas.bind('<B1-Motion>', self.__left_mouse_moving)  # move vertex or subdivide edge
        self.canvas.bind('<ButtonRelease-1>', self.__left_mouse_button_released)  # move vertex or subdivide edge
        self.region_window = region_window
        self.base_image = region_window.base_image
        self.base_array = np.array(self.base_image)

        self.tab = None
        self.mode = 'DEFAULT'
        self.rasters = [np.zeros(self.region_window.shape, dtype=int) for _ in range(N_REGIONS + 1)]
        self.polygons = [[] for _ in range(N_REGIONS + 1)]  # list of polygons for each tab
        self.movables = [[] for _ in range(N_REGIONS + 1)]  # vertices and centers of edges for polygons of a tab
        self._last_lb_click_event = None
        self.__double_click_flag = False
        self._create_crafted_image(0)

        self._create_mask()

    def to_tab(self, n):
        self.tab = n
        self.mode_default(None)
        self.update_raster(n)
        self._create_crafted_image(n)
        # self.region_window.on_ctrl(None)

    def update_raster(self, n):
        self.rasters[n] = np.zeros(self.region_window.shape, dtype=int)
        if n > 0:
            for p in self.polygons[n]:
                p = np.array(p)
                rr, cc = polygon(p[:, 0], p[:, 1], self.region_window.shape)
                self.rasters[n][rr, cc] = 1
        if n == 0:
            for m in range(1, N_REGIONS + 1):
                self.rasters[0][self.rasters[m] > 0] = m

    def update_movables(self, n):
        if n > 0:
            self.movables[n] = []
            for k in range(len(self.polygons[n])):
                p = self.polygons[n][k]
                for i in range(len(p)):
                    x, y = tuple(p[i])
                    x_, y_ = tuple(p[(i + 1) % len(p)])
                    self.movables[n] += [[x, y, n, k, i, 'vertex'],
                                         [(x + x_) // 2, (y + y_) // 2, n, k, i, 'edge']]

    def _create_crafted_image(self, n):
        crafted_image_array = self.base_array * 0.5 + get_color(self.rasters[n]) * 0.5
        self.crafted_image = misc.toimage(crafted_image_array, cmin=0, cmax=255)

    def mode_add_polygon(self, _ev):
        if self.tab > 0:
            self.mode = 'ADD'
            self.polygons[self.tab].append([])

    def mode_default(self, _ev):
        self.mode = 'DEFAULT'
        if len(self.polygons[self.tab]) > 0 and len(self.polygons[self.tab][-1]) < 3:
            self.polygons[self.tab].pop(-1)
            self.update_movables(self.tab)
            self.update_raster(self.tab)
            self._create_crafted_image(self.tab)

            self.__show_image()

    def __left_mouse_button_released(self, event):
        print('__left_mouse_button_released', self.__double_click_flag)

        if self.__double_click_flag:
            return
        self.region_window.root.after(300, self.__left_mouse_moving, event)

    def __left_mouse_moving(self, event):
        print('__left_mouse_moving', self.__double_click_flag)

        if self.__double_click_flag:
            self.__double_click_flag = False
            return

        coords = self._get_click_coordinates(event)
        if coords is None:
            return
        coords = [coords[1], coords[0]]
        ev = self._last_lb_click_event

        if self.mode == 'DEFAULT':
            if coords is not None and self.tab is not None and self.tab > 0 and ev is not None:
                _coords_old = [ev[0], ev[1]]
                n, k, i, type_ = tuple(ev[2:])
                if type_ == 'vertex':
                    self.polygons[n][k][i] = coords
                if type_ == 'edge':
                    self.polygons[n][k].insert(i + 1, coords)
                    self._last_lb_click_event = [coords[0], coords[1], n, k, i + 1, 'vertex']

        elif self.mode == 'ADD':
            self.polygons[self.tab][-1][-1] = coords

        self.update_movables(self.tab)
        self.update_raster(self.tab)
        self._create_crafted_image(self.tab)
        self.__show_image()

    def __left_mouse_button_pressed(self, event):
        print('__left_mouse_button_pressed', self.__double_click_flag)

        coords = self._get_click_coordinates(event)
        if coords is None:
            return
        coords = [coords[1], coords[0]]

        if self.mode == 'DEFAULT':
            if self.tab is not None and self.tab > 0:
                self._last_lb_click_event = self._find_nearest(self.tab, coords)
        elif self.tab > 0 and self.mode == 'ADD':
            self.polygons[self.tab][-1].append(coords)

        self.__show_image()

    def __left_mouse_double_click(self, event):
        print('__left_mouse_double_click', self.__double_click_flag)

        self.__double_click_flag = True

        coords = self._get_click_coordinates(event)

        if coords is not None and self.tab is not None and self.tab > 0:
            coords = [coords[1], coords[0]]
            nearest = self._find_nearest(self.tab, coords)
            if nearest is not None:
                n, k, i, type_ = tuple(nearest[2:])
                if type_ == 'vertex':
                    self.polygons[n][k].pop(i)
                    if len(self.polygons[n][k]) < 3:
                        self.polygons[n].pop(k)
                if type_ == 'edge':
                    self.polygons[n].pop(k)

        self.update_movables(self.tab)
        self.update_raster(self.tab)
        self._create_crafted_image(self.tab)
        self.__show_image()

    def _find_nearest(self, n, coords):
        if len(self.movables[n]) == 0:
            return None
        i = np.argmin([(p[0] - coords[0]) ** 2 + (p[1] - coords[1]) ** 2 for p in self.movables[n]])
        i = int(i)
        p = self.movables[n][i]
        if (p[0] - coords[0]) ** 2 + (p[1] - coords[1]) ** 2 > 5 ** 2:
            return None
        return self.movables[n][i]

    def __show_image(self):
        # noinspection PyUnresolvedReferences, PyProtectedMember
        super()._CanvasImage__show_image()
        self.canvas.delete('polygons')

        box_image = self.canvas.coords(self.container)
        for p in self.polygons[self.tab]:
            for i in range(len(p)):
                x, y = tuple(p[i])
                x, y = y, x

                x *= self.real_scale[0]
                y *= self.real_scale[1]

                x += box_image[0]
                y += box_image[1]

                x_, y_ = tuple(p[(i + 1) % len(p)])
                x_, y_ = y_, x_

                x_ *= self.real_scale[0]
                y_ *= self.real_scale[1]

                x_ += box_image[0]
                y_ += box_image[1]
                self.canvas.create_line(x, y, x_, y_, fill="#FADADD", width=3, tags='polygons')
                self.canvas.create_oval((x + x_) // 2 - 3, (y + y_) // 2 - 3, (x + x_) // 2 + 3, (y + y_) // 2 + 3,
                                        outline="#EFDECD", width=3, tags='polygons')

        for p in self.polygons[self.tab]:
            for i in range(len(p)):
                x, y = tuple(p[i])
                x, y = y, x

                x *= self.real_scale[0]
                y *= self.real_scale[1]

                x += box_image[0]
                y += box_image[1]

                self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5, outline="#EFDECD", width=3, tags='polygons')

    def patch_image(self, image):
        super().patch_image(image)
        self.__show_image()

    def _create_mask(self):
        x_min, x_max = self.region_window.hist[1][0], self.region_window.hist[1][-1]
        x_step = self.region_window.hist[1][1] - self.region_window.hist[1][0]
        y_min, y_max = self.region_window.hist[2][0], self.region_window.hist[2][-1]
        y_step = self.region_window.hist[2][1] - self.region_window.hist[2][0]
        channels = self.region_window.map_window.channels_region
        array = self.rasters[0]
        self.mask = Mask(x_min, x_max, x_step, y_min, y_max, y_step, array, channels)
        pass

import os
import sys

import numpy as np
from tkinter import ttk
from PIL import Image
import matplotlib.pyplot as plt
from tempfile import gettempdir

from matplotlib.colors import LinearSegmentedColormap, hsv_to_rgb
from screeninfo import get_monitors
from skimage.draw import polygon

from segcanvas.canvas import CanvasImage

TMP_FOLDER = gettempdir()  # system temp directory

SATELLITE_CHANNELS = {
    'LT04': {
        '01': 'blue',
        '02': 'green',
        '03': 'red',
        '04': 'nir',
        '05': 'swir1',
        '07': 'swir2'
    },
    'LT05': {
        '01': 'blue',
        '02': 'green',
        '03': 'red',
        '04': 'nir',
        '05': 'swir1',
        '07': 'swir2'
    },
    'LE07': {
        '01': 'blue',
        '02': 'green',
        '03': 'red',
        '04': 'nir',
        '05': 'swir1',
        '07': 'swir2'
    },
    'LC08': {
        '02': 'blue',
        '03': 'green',
        '04': 'red',
        '05': 'nir',
        '06': 'swir1',
        '07': 'swir2'
    },
    'S2AB': {
        '02': 'blue',
        '03': 'green',
        '04': 'red',
        '08': 'nir',
        '12': 'swir2'
    }
}


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

    def get_value(self, x, y):
        x_ = np.maximum(np.minimum(((x - self.x_min) // self.x_step).astype(int), self.array.shape[0] - 1), 0)
        y_ = np.maximum(np.minimum(((y - self.y_min) // self.y_step).astype(int), self.array.shape[1] - 1), 0)
        return self.array.flatten()[x_ * self.array.shape[1] + y_]

    def update_array(self, array):
        self.array = array


def get_color(t, colors):
    return np.array([colors.transpose()[i].take(t) for i in range(3)]).transpose((1, 2, 0))


class AugmentedLabelFrame(ttk.LabelFrame):
    def __init__(self, master):
        super().__init__(master)
        self.name = None
        self.number = None
        self.image = None


def string_to_value(s, dtype='int_to_str', logger=None):
    try:
        if dtype == 'int_to_str':
            n = int(s)
            if not 0 < n < 13:
                raise ValueError('Unknown Channel')
            return str(n).zfill(2)
        elif dtype == 'float':
            return float(s)
        elif dtype == 'int':
            return int(s)
    except Exception as e:
        if logger is not None:
            logger.log(e)
        return None


def plot_hist2d(hist):
    """2-dimensional array to Image"""
    array = hist.copy()
    array[0][:] = 0
    array[:][0] = 0

    array = array * 10000 // array.max()
    array[hist > 0] += 1
    array = array.astype(int)
    h, _ = np.histogram(array.flatten(), array.max() + 1)
    cdf = (h ** .5).cumsum()

    cmap = LinearSegmentedColormap.from_list('my_cmap',
                                             [hsv_to_rgb([0, 0, 0])] +
                                             [hsv_to_rgb([i / 1000, 1, 1]) for i in range(888, 20, -1)])
    fn = os.path.join(TMP_FOLDER, 'hist2d.png')
    plt.imsave(fn, cdf[array].transpose()[::-1, :], cmap=cmap)
    plt.close('all')
    return Image.open(fn).convert('RGB')


def plot_hist(x):
    """1-dimensional array to histogram Image"""
    q = x.flatten().copy()
    q = q[~np.isnan(q)]
    dpi = 100
    plt.figure(figsize=(380 / dpi, 300 / dpi), dpi=dpi)
    plt.hist(q, bins=256)
    fn = os.path.join(TMP_FOLDER, 'hist.png')
    plt.savefig(fn, figsize=(380 / dpi, 300 / dpi), dpi=dpi)
    plt.close('all')
    return Image.open(fn).convert('RGB')


class TabPolygonImage(CanvasImage):
    def __init__(self, canvas_frame, canvas, root, base_image, colors, n_tabs):
        super().__init__(canvas_frame, canvas)
        self.canvas.bind('<Button-1>', self._left_mouse_button_pressed)  # move vertex or subdivide edge
        self.canvas.bind('<Double-Button-1>', self._left_mouse_double_click)  # delete vertex or polygon
        self.canvas.bind('<B1-Motion>', self._left_mouse_moving)  # move vertex or subdivide edge
        self.canvas.bind('<ButtonRelease-1>', self._left_mouse_button_released)  # move vertex or subdivide edge
        self.base_image = base_image
        self.base_array = np.array(self.base_image).transpose([1, 0, 2])
        self.shape = self.base_array.shape[:2]
        self.root = root
        self.colors = colors

        self.tab = 0
        self.mode = 'DEFAULT'
        self.n_tabs = n_tabs
        self.rasters = [np.zeros(self.shape, dtype=int) for _ in range(self.n_tabs)]
        self.polygons = [[] for _ in range(self.n_tabs)]  # list of polygons for each tab
        self.movables = [[] for _ in range(self.n_tabs)]  # vertices and centers of edges for polygons of a tab
        self._last_lb_click_event = None
        self.__double_click_flag = False
        self._create_crafted_image(0)

    def reload_image(self, image, reset_canvas=True):
        super().reload_image(image, reset_canvas)
        self.base_image = image
        self.base_array = np.array(self.base_image).transpose([1, 0, 2])
        self.shape = self.base_array.shape[:2]
        self.rasters = [np.zeros(self.shape, dtype=int) for _ in range(self.n_tabs)]

    def to_tab(self, n):
        self.tab = n
        self.mode_default(None)
        self.update_raster(n)
        self._create_crafted_image(n)
        self._show_image()
        if self.crafted_image is not None:
            self.patch_image(self.crafted_image)
        else:
            self.patch_image(self.base_image)

    def update_raster(self, n):
        self.rasters[n] = np.zeros(self.shape, dtype=int)
        if n > 0:
            for p in self.polygons[n]:
                p = np.array(p)
                rr, cc = polygon(p[:, 0], p[:, 1], self.shape)
                self.rasters[n][rr, cc] = n
        if n == 0:
            for m in range(1, self.n_tabs):
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
        raster = self.rasters[n][:, ::-1]
        crafted_image_array = get_color(raster, self.colors)
        if n == 0:
            crafted_image_array = crafted_image_array * 0.5 + self.base_array * 0.5
        else:
            mask = np.array([raster == 0] * 3).transpose([1, 2, 0])
            crafted_image_array = crafted_image_array * (1 - mask) + self.base_array * mask
        self.crafted_image = Image.fromarray(crafted_image_array.astype('uint8').transpose([1, 0, 2]))

    def mode_add_polygon(self, _ev):
        if self.tab > 0:
            self.mode = 'ADD'

            if len(self.polygons[self.tab]) > 0 and len(self.polygons[self.tab][-1]) < 3:
                self.polygons[self.tab].pop(-1)
                self.update_movables(self.tab)

            self.polygons[self.tab].append([])

    def mode_default(self, _ev):
        self.mode = 'DEFAULT'
        if len(self.polygons[self.tab]) > 0 and len(self.polygons[self.tab][-1]) < 3:
            self.polygons[self.tab].pop(-1)
            self.update_movables(self.tab)
            self.update_raster(self.tab)
            self._create_crafted_image(self.tab)

            self.patch_image(self.crafted_image)

    def _left_mouse_button_released(self, event):
        if self.__double_click_flag:
            return
        self.root.after(300, self._left_mouse_moving, event)

    def _left_mouse_moving(self, event):
        if self.__double_click_flag:
            self.__double_click_flag = False
            return

        coords = self.get_click_coordinates(event)
        if coords is None:
            return
        ev = self._last_lb_click_event

        if self.mode == 'DEFAULT':
            if coords is not None and self.tab is not None and self.tab > 0 and ev is not None:
                _coords_old = [ev[0], ev[1]]
                n, k, i, type_ = tuple(ev[2:])
                if type_ == 'vertex':
                    self.polygons[n][k][i] = [coords[0], coords[1]]
                if type_ == 'edge':
                    self.polygons[n][k].insert(i + 1, [coords[0], coords[1]])
                    self._last_lb_click_event = [coords[0], coords[1], n, k, i + 1, 'vertex']

        elif self.mode == 'ADD':
            self.polygons[self.tab][-1][-1] = [coords[0], coords[1]]

        self.update_movables(self.tab)
        self.update_raster(self.tab)
        self._create_crafted_image(self.tab)
        self.patch_image(self.crafted_image)

    def _left_mouse_button_pressed(self, event):
        coords = self.get_click_coordinates(event)
        if coords is None:
            return

        if self.mode == 'DEFAULT':
            if self.tab is not None and self.tab > 0:
                self._last_lb_click_event = self._find_nearest(self.tab,
                                                               [coords[0], coords[1]])
        elif self.tab > 0 and self.mode == 'ADD':
            self.polygons[self.tab][-1].append([coords[0], coords[1]])

        self._show_image()

    def _left_mouse_double_click(self, event):
        self.__double_click_flag = True

        coords = self.get_click_coordinates(event)

        if coords is not None and self.tab is not None and self.tab > 0:
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
        self.patch_image(self.crafted_image)

    def _find_nearest(self, n, coords):
        if len(self.movables[n]) == 0:
            return None
        i = np.argmin([(p[0] - coords[0]) ** 2 + (p[1] - coords[1]) ** 2 for p in self.movables[n]])
        i = int(i)
        p = self.movables[n][i]
        if (p[0] - coords[0]) ** 2 + (p[1] - coords[1]) ** 2 > 5 ** 2:
            return None
        return self.movables[n][i]

    def get_click_coordinates(self, event):
        res = super()._get_click_coordinates(event)
        if res is not None:
            return res[0], self.shape[1] - res[1]
        return None

    def _show_image(self):
        super()._show_image()
        self.canvas.delete('polygons')

        box_image = self.canvas.coords(self.container)
        for p in self.polygons[self.tab]:
            for i in range(len(p)):
                x, y = tuple(p[i])
                y = self.shape[1] - y

                x *= self.real_scale[0]
                y *= self.real_scale[1]

                x += box_image[0]
                y += box_image[1]

                x_, y_ = tuple(p[(i + 1) % len(p)])
                y_ = self.shape[1] - y_

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
                y = self.shape[1] - y

                x *= self.real_scale[0]
                y *= self.real_scale[1]

                x += box_image[0]
                y += box_image[1]

                self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5, outline="#EFDECD", width=3, tags='polygons')

    def patch_image(self, image):
        super().patch_image(image)
        self._show_image()


def copy_list(arg):
    return [a.copy() for a in arg]


class Keycode2Char:
    linux_table = {39: 's', 32: 'o', 36: 'enter', 19: '0'}
    linux_table.update({9 + n: str(n) for n in range(1, 10)})

    win_table = {83: 's', 79: 'o', 13: 'enter'}
    win_table.update({48 + n: str(n) for n in range(10)})

    @classmethod
    def __call__(cls, n):
        if sys.platform == 'linux':
            table = cls.linux_table
        elif sys.platform == 'win32':
            table = cls.win_table
        else:
            raise Exception('Platform unknown')
        if n in table:
            return table[n]
        return ''


def load_proj():
    if getattr(sys, 'frozen', False):  # if we are inside .exe
        # noinspection PyUnresolvedReferences, PyProtectedMember
        os.environ['PROJ_LIB'] = os.path.join(sys._MEIPASS, 'proj')
    # elif sys.platform == 'win32':
    #     os.environ['PROJ_LIB'] = os.path.join(os.path.split(sys.executable)[0], 'Library', 'share', 'proj')


keycode2char = Keycode2Char()


def _calc_geom():
    monitors = get_monitors()
    i = int(np.argmax([m.height * m.width for m in monitors]))
    m = monitors[i]
    h, w, x, y = m.height, m.width, m.x, m.y
    g_map = tuple(map(int, (w * 0.55, h * 0.7, y + w * .02, x + h * .05)))  # w, h, y, x
    g_hist = tuple(map(int, (w * 0.4, w * 0.4, g_map[2] + g_map[0] + w * .02, g_map[3])))
    return g_map, g_hist


geometry_map, geometry_histogram = _calc_geom()

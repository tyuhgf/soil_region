import json
import tkinter as tk
from tkinter import ttk
import tkinter.filedialog as tk_filedialog
import numpy as np
from scipy import misc
from skimage.draw import polygon

from segcanvas.canvas import CanvasImage
from utils import Mask, NamedFrame, N_REGIONS, plot_hist, get_color

from segcanvas.wrappers import FocusLabelFrame


class RegionWindow:
    def __init__(self, map_window, hist):
        self.app = map_window.app
        self.root = tk.Toplevel(self.app)
        self.root.title('Region')
        self.root.geometry("%dx%d%+d%+d" % (600, 600, 500, 100))
        self.map_window = map_window
        self.hist = hist

        self.shape = hist[0].shape

        self._add_top_menu()
        self._add_tabs()
        self.base_image = plot_hist(hist[0])
        self._add_canvas_frame()
        self.canvas_image.reload_image(self.base_image)

        self.root.bind('<Control_L>', self.on_ctrl)
        self.root.bind('<KeyRelease>', self.redraw)
        self.root.bind('<space>', self.mode_add_polygon)
        self.root.bind('<Escape>', self.mode_default)

    def _add_top_menu(self):
        self.top_menu = tk.Frame(self.root, height=60, bg='gray')
        self.top_menu.pack(side='top', fill='x')

        self.load_btn = tk.Button(self.top_menu, text='Load\nRegion')
        self.save_btn = tk.Button(self.top_menu, text='Save\nRegion')
        self.quit_btn = tk.Button(self.top_menu, text='Quit')
        self.to_map_btn = tk.Button(self.top_menu, text='Update\nMap')

        self.load_btn.bind("<Button-1>", self._load_file)
        self.save_btn.bind("<Button-1>", self.save_file)
        self.quit_btn.bind("<Button-1>", self.quit)
        self.to_map_btn.bind("<Button-1>", self.redraw_map_window)

        self.load_btn.place(x=10, y=10, width=40, height=40)
        self.save_btn.place(x=60, y=10, width=40, height=40)
        self.quit_btn.place(x=110, y=10, width=40, height=40)
        self.to_map_btn.place(x=-50, y=10, relx=1, width=40, height=40)

    def _add_canvas_frame(self):
        canvas_frame = FocusLabelFrame(self.root)
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        canvas = tk.Canvas(canvas_frame, highlightthickness=0, cursor="hand1", width=400, height=400)
        canvas.grid(row=0, column=0, sticky='nswe', padx=5, pady=5)
        canvas_frame.pack(side=tk.LEFT, fill="both", expand=True, padx=5, pady=5)
        self.canvas = canvas
        self.canvas_frame = canvas_frame
        self.canvas_image = RegionImage(self.canvas_frame, self.canvas, self)

    def _add_tabs(self):
        self.tab_parent = ttk.Notebook(self.root)
        self.tabs = [NamedFrame(self.tab_parent, name=f'color{i}', number=i) for i in range(N_REGIONS + 1)]
        self.tabs[0].name = 'all'

        for t in self.tabs:
            self.tab_parent.add(t, text=t.name)
            t.bind('<Visibility>', self._activate_tab)

        self.tab_parent.pack(fill='x', side='top')

    def _activate_tab(self, ev):
        if hasattr(self, 'canvas_image'):
            self.canvas_image.to_tab(ev.widget.number)

    def quit(self, _ev):
        delattr(self.map_window, 'region_window')
        self.map_window.map_image.filtered_image = None
        self.root.destroy()
        del self

    def _load_file(self, _ev):
        load_path = tk_filedialog.Open(self.root, filetypes=[('', '*.json')]).show()
        if load_path == '':
            return
        x_min, x_max = self.hist[1][0], self.hist[1][-1]
        x_step = self.hist[1][1] - self.hist[1][0]
        y_min, y_max = self.hist[2][0], self.hist[2][-1]
        y_step = self.hist[2][1] - self.hist[2][0]
        channels = self.map_window.channels_region

        q = json.load(open(load_path, 'r'))
        if q['channels'] != channels:
            return  # todo message box
        for channel_polygons in q['polygons']:
            for p in channel_polygons:
                for v in p:
                    v[0] = min(max(int((q['x_min'] + v[0] * q['x_step'] - x_min) / x_step), 0), self.shape[0] - 1)
                    v[1] = min(max(int((q['y_min'] + v[1] * q['y_step'] - y_min) / y_step), 0), self.shape[1] - 1)
        self.canvas_image.polygons = q['polygons']
        for i in reversed(range(len(self.canvas_image.polygons))):
            self.canvas_image.update_raster(i)
        self.canvas_image.to_tab(0)

    def save_file(self, _ev):
        fn = tk_filedialog.SaveAs(self.root, initialfile='region.json', filetypes=[('*.json files', '*.json')]).show()
        if fn == '':
            return
        if not fn.endswith('.json'):
            fn += '.json'
        x_min, x_max = self.hist[1][0], self.hist[1][-1]
        x_step = self.hist[1][1] - self.hist[1][0]
        y_min, y_max = self.hist[2][0], self.hist[2][-1]
        y_step = self.hist[2][1] - self.hist[2][0]
        channels = self.map_window.channels_region
        json.dump({
            'channels': channels,
            'x_min': x_min,
            'x_max': x_max,
            'x_step': x_step,
            'y_min': y_min,
            'y_max': y_max,
            'y_step': y_step,
            'polygons': self.canvas_image.polygons
        }, open(fn, 'w'), indent=4)

    def on_ctrl(self, _arg):
        self.canvas_image.patch_image(self.base_image)

    def redraw(self, _arg):
        if self.canvas_image.crafted_image is not None:
            self.canvas_image.patch_image(self.canvas_image.crafted_image)
        else:
            self.on_ctrl(None)

    def redraw_map_window(self, _arg):
        self.canvas_image.mask.update_array(self.canvas_image.rasters[self.canvas_image.tab])
        self.map_window.map_image.mask = self.canvas_image.mask
        self.map_window.map_image.create_filtered_image()
        self.map_window.redraw()

    def mode_add_polygon(self, ev):
        return self.canvas_image.mode_add_polygon(ev)

    def mode_default(self, ev):
        return self.canvas_image.mode_default(ev)


class RegionImage(CanvasImage):
    def __init__(self, canvas_frame, canvas, region_window):
        super().__init__(canvas_frame, canvas)
        self.canvas.bind('<Button-1>', self.__left_mouse_button_pressed)  # move vertex or subdivide edge
        self.canvas.bind('<Double-Button-1>', self.__left_mouse_double_click)  # delete vertex or polygon
        self.canvas.bind('<B1-Motion>', self.__left_mouse_moving)  # move vertex or subdivide edge
        self.canvas.bind('<ButtonRelease-1>', self.__left_mouse_button_released)  # move vertex or subdivide edge
        self.region_window = region_window
        self.base_image = region_window.base_image
        self.base_array = np.array(self.base_image).transpose([1, 0, 2])

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
        self.__show_image()
        self.region_window.redraw(None)

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
        raster = self.rasters[n][:, ::-1]
        crafted_image_array = get_color(raster)
        if n == 0:
            crafted_image_array = crafted_image_array * 0.5 + self.base_array * 0.5
        else:
            mask = np.array([raster == 0] * 3).transpose([1, 2, 0])
            crafted_image_array = crafted_image_array * (1 - mask) + self.base_array * mask
        self.crafted_image = misc.toimage(crafted_image_array.transpose(1, 0, 2), cmin=0, cmax=255)

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

            self.patch_image(self.crafted_image)

    def __left_mouse_button_released(self, event):
        if self.__double_click_flag:
            return
        self.region_window.root.after(300, self.__left_mouse_moving, event)

    def __left_mouse_moving(self, event):
        if self.__double_click_flag:
            self.__double_click_flag = False
            return

        coords = self._get_click_coordinates(event)
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

    def __left_mouse_button_pressed(self, event):
        coords = self._get_click_coordinates(event)
        if coords is None:
            return

        if self.mode == 'DEFAULT':
            if self.tab is not None and self.tab > 0:
                self._last_lb_click_event = self._find_nearest(self.tab,
                                                               [coords[0], coords[1]])
        elif self.tab > 0 and self.mode == 'ADD':
            self.polygons[self.tab][-1].append([coords[0], coords[1]])

        self.__show_image()

    def __left_mouse_double_click(self, event):
        self.__double_click_flag = True

        coords = self._get_click_coordinates(event)

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

    def _get_click_coordinates(self, event):
        res = super()._get_click_coordinates(event)
        if res is not None:
            return res[0], self.region_window.shape[1] - res[1]
        return None

    def __show_image(self):
        # noinspection PyUnresolvedReferences, PyProtectedMember
        super()._CanvasImage__show_image()
        self.canvas.delete('polygons')

        box_image = self.canvas.coords(self.container)
        for p in self.polygons[self.tab]:
            for i in range(len(p)):
                x, y = tuple(p[i])
                y = self.region_window.shape[1] - y

                x *= self.real_scale[0]
                y *= self.real_scale[1]

                x += box_image[0]
                y += box_image[1]

                x_, y_ = tuple(p[(i + 1) % len(p)])
                y_ = self.region_window.shape[1] - y_

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
                y = self.region_window.shape[1] - y

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

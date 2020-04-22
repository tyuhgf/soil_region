import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.filedialog as tk_filedialog
from tkinter.colorchooser import askcolor
from tkinter.messagebox import showwarning

import numpy as np
from PIL import Image, ImageTk
from skimage.draw import polygon

from segcanvas.canvas import CanvasImage
from utils import Mask, plot_hist2d, get_color, AugmentedLabelFrame

from segcanvas.wrappers import FocusLabelFrame


class RegionWindow:
    def __init__(self, map_window, hist, base_image=None):
        self.app = map_window.app
        self.root = tk.Toplevel(self.app)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.title('SoilRegion (Region)')
        self.root.geometry("%dx%d%+d%+d" % (900, 900, 500, 100))
        self.map_window = map_window
        self.hist = hist

        self.shape = hist[0].shape

        self._add_top_menu()
        self.n_tabs = map_window.n_regions + 1
        self._add_tabs()
        self.base_image = base_image or plot_hist2d(hist[0])
        self._add_canvas_frame()
        self.canvas_image.reload_image(self.base_image)
        self._load_colors(load_path='colors.json')

        self.root.bind('<Shift_L>', self.on_shift)
        self.root.bind('<KeyRelease>', self.redraw)
        self.root.bind('<space>', self.mode_add_polygon)
        self.root.bind('<Escape>', self.mode_default)
        self.root.bind('<Control-KeyPress>', self._ctrl_callback)

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

        self.tabs = []
        for i in range(self.n_tabs):
            self.tabs.append(AugmentedLabelFrame(self.tab_parent))
            self.tabs[-1].name = f'color{i}' if i > 0 else 'all'
            self.tabs[-1].number = i
            self.tabs[-1].image = ImageTk.PhotoImage(Image.fromarray(np.array(
                [[self.map_window.colors[i] for _ in range(20)] for _ in range(20)], dtype='uint8'), mode='RGB'))

            self.tab_parent.add(self.tabs[-1], text=self.tabs[-1].name, image=self.tabs[-1].image, compound='right')
            self.tabs[-1].bind('<Visibility>', self._activate_tab)
        self.tab_parent.bind('<Double-Button-1>', self._choose_color)
        self.tab_parent.bind('<Double-Button-3>', self._save_or_load_colors)

        self.tab_parent.pack(fill='x', side='top')

    def _activate_tab(self, ev):
        if hasattr(self, 'canvas_image'):
            self.canvas_image.to_tab(ev.widget.number)

    def _choose_color(self, _ev, n=None, color='ask'):
        n = n or self.canvas_image.tab or 0
        if n == 0:
            return
        if color == 'ask':
            color = askcolor(initialcolor='#%02x%02x%02x' % tuple(self.map_window.colors[n]))[0]
        if color is not None:
            self.map_window.colors[n] = np.array(color, dtype=int)
            self.tabs[n].image = ImageTk.PhotoImage(Image.fromarray(
                np.array([[self.map_window.colors[n] for _ in range(20)] for _ in range(20)], dtype='uint8'),
                mode='RGB'))
            self.tab_parent.tab(n, text=self.tabs[n].name, image=self.tabs[n].image, compound='right')
            if n == self.canvas_image.tab:
                self.canvas_image.to_tab(n)  # update current image

    def _save_colors(self, _ev=None):
        if hasattr(self, 'save_or_load_colors_window'):
            self.save_or_load_colors_window.destroy()
        fn = tk_filedialog.SaveAs(self.root, initialfile='colors.json', filetypes=[('*.json files', '*.json')]).show()
        if fn == '':
            return
        if not fn.endswith('.json'):
            fn += '.json'
        json.dump({
            'colors': self.map_window.colors.tolist()
        }, open(fn, 'w'), indent=4)

    def _load_colors(self, _ev=None, load_path=None):
        if hasattr(self, 'save_or_load_colors_window'):
            self.save_or_load_colors_window.destroy()
        load_path = load_path or tk_filedialog.Open(self.root, filetypes=[('', '*.json')]).show()
        if load_path == '' or not os.path.isfile(load_path):
            return
        q = json.load(open(load_path, 'r'))
        for i in range(len(q['colors'])):
            self._choose_color(None, n=i, color=q['colors'][i])

    def _save_or_load_colors(self, _ev):
        self.save_or_load_colors_window = tk.Toplevel(self.root)
        self.save_or_load_colors_window.title('Save or Load Colors?')
        message = 'Save or Load Colors?'
        tk.Label(self.save_or_load_colors_window, text=message).pack()
        tk.Button(self.save_or_load_colors_window, text='Save', command=self._save_colors).pack()
        tk.Button(self.save_or_load_colors_window, text='Load', command=self._load_colors).pack()

    def quit(self, _ev=None):
        if messagebox.askyesno(title="Quit?", message="Closing window may cause data loss."):
            delattr(self.map_window, 'region_window')
            self.map_window.map_image.filtered_image = None
            self.root.destroy()
            del self

    def _load_file(self, _ev):
        load_path = tk_filedialog.Open(self.root, filetypes=[('', '*.json')]).show()
        if not isinstance(load_path, str) or load_path == '':
            return
        x_min, x_max = self.hist[1][0], self.hist[1][-1]
        x_step = self.hist[1][1] - self.hist[1][0]
        y_min, y_max = self.hist[2][0], self.hist[2][-1]
        y_step = self.hist[2][1] - self.hist[2][0]
        channels = self.map_window.channels_region

        q = json.load(open(load_path, 'r'))
        if q['channels'] != channels:
            showwarning('Warning', 'Cannot load region with wrong channels!')
            return
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
        fn = tk_filedialog.SaveAs(self.root, initialfile=f'{self.map_window.img_name}_region.json',
                                  filetypes=[('*.json files', '*.json')]).show()
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

    def on_shift(self, _arg):
        self.canvas_image.patch_image(self.base_image)

    def redraw(self, _arg):
        if self.canvas_image.crafted_image is not None:
            self.canvas_image.patch_image(self.canvas_image.crafted_image)
        else:
            self.on_shift(None)

    def redraw_map_window(self, _arg):
        self.canvas_image.mask.update_array(self.canvas_image.rasters[self.canvas_image.tab])
        self.map_window.map_image.mask = self.canvas_image.mask
        self.map_window.map_image.create_filtered_image()
        self.map_window.redraw()

    def mode_add_polygon(self, ev):
        return self.canvas_image.mode_add_polygon(ev)

    def mode_default(self, ev):
        return self.canvas_image.mode_default(ev)

    def _ctrl_callback(self, ev):
        if ev.keycode == 83:  # s
            self.save_file(None)
        if ev.keycode == 79:  # o
            self._load_file(None)


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
        self.n_tabs = region_window.n_tabs
        self.rasters = [np.zeros(self.region_window.shape, dtype=int) for _ in range(self.n_tabs)]
        self.polygons = [[] for _ in range(self.n_tabs)]  # list of polygons for each tab
        self.movables = [[] for _ in range(self.n_tabs)]  # vertices and centers of edges for polygons of a tab
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
        crafted_image_array = get_color(raster, self.region_window.map_window.colors)
        if n == 0:
            crafted_image_array = crafted_image_array * 0.5 + self.base_array * 0.5
        else:
            mask = np.array([raster == 0] * 3).transpose([1, 2, 0])
            crafted_image_array = crafted_image_array * (1 - mask) + self.base_array * mask
        self.crafted_image = Image.fromarray(crafted_image_array.astype('uint8').transpose(1, 0, 2))

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

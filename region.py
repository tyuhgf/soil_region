import tkinter as tk
import tkinter.filedialog as tk_filedialog
from tkinter import ttk
import numpy as np
from PIL import Image
from scipy import misc
import matplotlib.pyplot as plt

import utils
from utils import RegionImage, NamedFrame, N_REGIONS

from segcanvas.canvas import CanvasImage
from segcanvas.wrappers import FocusLabelFrame


class RegionWindow:
    def __init__(self, map_window, hist):
        self.app = map_window.app
        self.root = tk.Toplevel(self.app)
        self.map_window = map_window
        self.hist = hist

        self.shape = hist[0].shape

        self._add_top_menu()
        self._add_tabs()
        self._add_left_menu()
        self._calc_base_image(hist[0])
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
        # todo: reconfigure button & _reconfigure method

        self.load_btn.bind("<Button-1>", self._load_file)
        self.save_btn.bind("<Button-1>", self.save_file)
        self.quit_btn.bind("<Button-1>", self.quit)
        self.to_map_btn.bind("<Button-1>", self.redraw_map_window)

        self.load_btn.place(x=10, y=10, width=40, height=40)
        self.save_btn.place(x=60, y=10, width=40, height=40)
        self.quit_btn.place(x=110, y=10, width=40, height=40)
        self.to_map_btn.place(x=-50, y=10, relx=1, width=40, height=40)

    def _calc_base_image(self, array):
        plt.imsave('C:\\Temp\\qwe.png', array, cmap='gnuplot2')
        self.base_image = Image.open('C:\\Temp\\qwe.png').convert('RGB')

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
        # self.canvas_image.register_click_callback(self._click_callback)

    def _click_callback(self, is_positive, x, y):
        if not is_positive:  # right button
            return
        print(x, y)

    def _add_left_menu(self):
        pass

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
        self.root.destroy()  # todo delete images

    def _load_file(self, _ev):
        pass  # todo

    def save_file(self, ev):
        pass  # todo

    def on_ctrl(self, _arg):
        self.canvas_image.patch_image(self.base_image)

    def redraw(self, _arg):
        if self.canvas_image.crafted_image is not None:
            self.canvas_image.patch_image(self.canvas_image.crafted_image)
        else:
            self.on_ctrl(None)

    def redraw_map_window(self, _arg):
        self.canvas_image.mask.update_array(self.canvas_image.rasters[0])
        self.map_window.map_image.mask = self.canvas_image.mask
        self.map_window.map_image.create_filtered_image()
        pass  # todo

    def mode_add_polygon(self, ev):
        return self.canvas_image.mode_add_polygon(ev)

    def mode_default(self, ev):
        return self.canvas_image.mode_default(ev)

import tkinter as tk
import tkinter.filedialog as tk_filedialog
import numpy as np
from PIL import Image
from scipy import misc

import utils
from region import RegionWindow
from utils import MapImage

from segcanvas.canvas import CanvasImage
from segcanvas.wrappers import FocusLabelFrame


class MapWindow:
    def __init__(self, app):
        self.app = app
        self.root = app

        self._add_top_menu()
        self._add_left_menu()
        self._add_canvas_frame()
        self.map_image = MapImage()
        self.channels_img = ['07', '04', '02']
        self.channels_region = ['03', '04']

        self.root.bind('<Control_L>', self.on_ctrl)
        self.root.bind('<KeyRelease>', self.redraw)

    def _add_top_menu(self):
        self.top_menu = tk.Frame(self.root, height=60, bg='gray')
        self.top_menu.pack(side='top', fill='x')

        self.load_btn = tk.Button(self.top_menu, text='Load\nImage')
        self.save_btn = tk.Button(self.top_menu, text='Save\nImage')
        self.quit_btn = tk.Button(self.top_menu, text='Quit')
        self.to_region_btn = tk.Button(self.top_menu, text='Draw\nRegion')
        # todo: reconfigure button & _reconfigure method

        self.load_btn.bind("<Button-1>", self._load_file)
        self.save_btn.bind("<Button-1>", self.save_file)
        self.quit_btn.bind("<Button-1>", self.quit)
        self.to_region_btn.bind("<Button-1>", self._open_region_window)

        self.load_btn.place(x=10, y=10, width=40, height=40)
        self.save_btn.place(x=60, y=10, width=40, height=40)
        self.quit_btn.place(x=110, y=10, width=40, height=40)
        self.to_region_btn.place(x=-50, y=10, relx=1, width=40, height=40)

    def _add_canvas_frame(self):
        canvas_frame = FocusLabelFrame(self.root)
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        canvas = tk.Canvas(canvas_frame, highlightthickness=0, cursor="hand1", width=400, height=400)
        canvas.grid(row=0, column=0, sticky='nswe', padx=5, pady=5)
        canvas_frame.pack(side=tk.LEFT, fill="both", expand=True, padx=5, pady=5)
        self.canvas = canvas
        self.canvas_frame = canvas_frame
        self.canvas_image = CanvasImage(self.canvas_frame, self.canvas)

    def _add_left_menu(self):
        pass

    def quit(self, _ev):
        self.root.destroy()

    def _load_file(self, _ev):
        img_path = tk_filedialog.Open(self.root, filetypes=[('', '*.*')]).show()
        if img_path != '':
            if hasattr(self, 'canvas_image'):
                pass  # todo remove self.canvas_image data from memory
            self.map_image.load(img_path)
            self.map_image.create_original_img(self.channels_img)
            # self.map_image.mask = utils.get_default_mask(self.map_image)
            # self.map_image.create_filtered_image()
            self.canvas_image.reload_image(self.map_image.original_image, True)

    def save_file(self, ev):
        pass  # todo
        # fn = tk_filedialog.SaveAs(self.root, filetypes=[('*.txt files', '.txt')]).show()
        # if fn == '':
        #     return

    def on_ctrl(self, _arg):
        self.canvas_image.patch_image(self.map_image.original_image)

    def redraw(self, _arg):
        if self.map_image.filtered_image is not None:
            self.canvas_image.patch_image(self.map_image.filtered_image)
        else:
            self.on_ctrl(None)

    def _open_region_window(self, _arg):
        if hasattr(self, 'region_window'):
            self.region_window.quit(None)

        array = [self.map_image.bands[self.map_image.chan_dict[c]] for c in self.channels_region]
        hist = np.histogram2d(array[0].flatten(), array[1].flatten(), bins=[100, 100])  # todo params from json ordialog

        self.region_window = RegionWindow(self, hist)


if __name__ == '__main__':
    _app = tk.Tk()
    MapWindow(_app)
    _app.mainloop()

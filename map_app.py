import tkinter as tk
import tkinter.filedialog as tk_filedialog

import numpy as np
from PIL import Image
from scipy import misc

from region_dialog_window import RegionDialogWindow
from utils import string_to_value, get_color

from segcanvas.canvas import CanvasImage
from segcanvas.wrappers import FocusLabelFrame


class MapWindow:
    def __init__(self, app):
        self.app = app
        self.root = app
        self.root.title('Preview')
        self.root.geometry("%dx%d%+d%+d" % (700, 700, 100, 100))

        self.channels_img = ['07', '04', '02']
        self._add_top_menu()
        self._add_left_menu()
        self._add_canvas_frame()
        self.map_image = MapImage()

        self.root.bind('<Control_L>', self.on_ctrl)
        self.root.bind('<KeyRelease>', self.redraw)

    def _add_top_menu(self):
        self.top_menu = tk.Frame(self.root, height=60, bg='gray')
        self.top_menu.pack(side='top', fill='x')

        self.load_btn = tk.Button(self.top_menu, text='Load\nImage')
        self.save_btn = tk.Button(self.top_menu, text='Save\nImage')
        self.quit_btn = tk.Button(self.top_menu, text='Quit')
        self.to_region_btn = tk.Button(self.top_menu, text='Draw\nRegion')

        self.load_btn.bind("<Button-1>", self._load_file)
        self.save_btn.bind("<Button-1>", self.save_file)
        self.quit_btn.bind("<Button-1>", self.quit)
        self.to_region_btn.bind("<Button-1>", self._open_region_dialog_window)

        self.load_btn.place(x=10, y=10, width=40, height=40)
        self.save_btn.place(x=60, y=10, width=40, height=40)
        self.quit_btn.place(x=110, y=10, width=40, height=40)
        self.to_region_btn.place(x=-50, y=10, relx=1, width=40, height=40)

        self.ch_stringvars = [tk.StringVar() for _ in range(3)]
        self.ch_entries = [tk.Entry(self.top_menu, textvariable=v) for v in self.ch_stringvars]
        for i, e in enumerate(self.ch_entries):
            e.place(x=160 + 30*i, y=10, width=25)
            e.delete(0, -1)
            e.insert(0, int(self.channels_img[i]))
            e.bind('<Return>', self.reload_channels)

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

    def reload_channels(self, _ev):
        for i in range(3):
            self.channels_img[i] = string_to_value(self.ch_stringvars[i].get()) or self.channels_img[i]
            self.ch_entries[i].delete(0, 'end')
            self.ch_entries[i].insert(0, int(self.channels_img[i]))
        if self.map_image.original_image is not None:
            self.map_image.create_original_img(self.channels_img)
            self.canvas_image.reload_image(self.map_image.original_image, True)

    def _load_file(self, _ev):
        img_path = tk_filedialog.Open(self.root, filetypes=[('', '*.*')]).show()
        if img_path != '':
            if hasattr(self, 'canvas_image'):
                pass  # todo remove self.canvas_image data from memory
            self.map_image.load(img_path)
            self.map_image.create_original_img(self.channels_img)
            # self.map_image.mask = utils.get_default_mask(self.map_image)  # todo delete
            # self.map_image.create_filtered_image()
            self.canvas_image.reload_image(self.map_image.original_image, True)

    def save_file(self, ev):
        pass  # todo
        # fn = tk_filedialog.SaveAs(self.root, filetypes=[('*.txt files', '.txt')]).show()
        # if fn == '':
        #     return

    def on_ctrl(self, _arg):
        if self.map_image.original_image is not None:
            self.canvas_image.patch_image(self.map_image.original_image)

    def redraw(self, _arg=None):
        if self.map_image.filtered_image is not None:
            self.canvas_image.patch_image(self.map_image.filtered_image)
        else:
            self.on_ctrl(None)

    def _open_region_dialog_window(self, _arg):
        if hasattr(self, 'region_window'):
            self.region_window.quit(None)
        if hasattr(self, 'region_dialog_window'):
            self.region_dialog_window.quit(None)

        self.region_dialog_window = RegionDialogWindow(self)


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
        self.original_image = misc.toimage(np.array(arrays))
        # Image.fromarray(np.array(arrays).transpose([1,2,0]), mode='RGB') ???
        self.original_array = np.array(self.original_image)

    def create_filtered_image(self):
        arrays = [self.bands[self.chan_dict[c]] for c in self.mask.channels]

        types = self.mask.get_value(*tuple(arrays))
        colors = get_color(types)
        filtered_image_array = self.original_array * 0.5 + colors * 0.5
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


if __name__ == '__main__':
    _app = tk.Tk()
    MapWindow(_app)
    _app.mainloop()

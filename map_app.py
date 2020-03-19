import tkinter as tk
import tkinter.filedialog as tk_filedialog

import numpy as np
from scipy import misc
import gdal

from region_dialog_window import RegionDialogWindow
from utils import string_to_value, get_color

from segcanvas.canvas import CanvasImage
from segcanvas.wrappers import FocusLabelFrame


class MapWindow:
    def __init__(self, app):
        self.app = app
        self.root = app
        self.root.title('Map')
        self.root.geometry("%dx%d%+d%+d" % (700, 700, 100, 100))

        self.channels_img = ['07', '04', '02']
        self._add_top_menu()
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
        self.slider = tk.Scale(self.top_menu, from_=1, to=42, orient='horizontal',
                               command=self._delayed_reload_channels)
        self.slider.set(10)

        self.load_btn.bind("<Button-1>", self._load_file)
        self.save_btn.bind("<Button-1>", self.save_file)
        self.quit_btn.bind("<Button-1>", self.quit)
        self.to_region_btn.bind("<Button-1>", self._open_region_dialog_window)

        self.load_btn.place(x=10, y=10, width=40, height=40)
        self.save_btn.place(x=60, y=10, width=40, height=40)
        self.quit_btn.place(x=110, y=10, width=40, height=40)
        self.to_region_btn.place(x=-50, y=10, relx=1, width=40, height=40)
        self.slider.place(x=270, y=10)

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

    def quit(self, _ev):
        self.root.destroy()

    def _delayed_reload_channels(self, _ev):
        if not hasattr(self, '_job'):
            self._job = None
        if self._job:
            self.root.after_cancel(self._job)
        self._job = self.root.after(100, self.reload_channels)

    def reload_channels(self, _ev=None):
        for i in range(3):
            self.channels_img[i] = string_to_value(self.ch_stringvars[i].get()) or self.channels_img[i]
            self.ch_entries[i].delete(0, 'end')
            self.ch_entries[i].insert(0, int(self.channels_img[i]))
        if self.map_image.original_image is not None:
            self.map_image.create_original_img(self.channels_img, self.slider.get())
            self.canvas_image.reload_image(self.map_image.original_image, True)

    def _load_file(self, _ev):
        img_path = tk_filedialog.Open(self.root, filetypes=[('*.tif files', '*.tif')]).show()
        if img_path != '':
            self.map_image.load(img_path)
            self.map_image.create_original_img(self.channels_img, self.slider.get())
            self.canvas_image.reload_image(self.map_image.original_image, True)

    def save_file(self, _ev):
        fn = tk_filedialog.SaveAs(self.root, filetypes=[('*.tif files', '*.tif')]).show()
        if fn == '':
            return
        if not fn.endswith('.tif'):
            fn += '.tif'
        arrays = [self.map_image.bands[self.map_image.chan_dict[c]] for c in self.map_image.mask.channels]
        # todo revisit logic create_filtered_image
        types = self.map_image.mask.get_value(*tuple(arrays))

        driver = gdal.GetDriverByName("GTiff")
        outdata = driver.Create(fn, types.shape[1], types.shape[0], 1, gdal.GDT_UInt16)
        outdata.SetGeoTransform(self.map_image.meta_dict['geotransform'])
        outdata.SetProjection(self.map_image.meta_dict['projection'])
        outdata.GetRasterBand(1).WriteArray(types)
        outdata.FlushCache()  # saves to disk

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
        self.meta_dict = None

    def load_band(self, b, img_path):
        ds = gdal.Open(img_path)
        if ds is None:
            return
        band = ds.GetRasterBand(1)
        self.bands[b] = band.ReadAsArray()
        self.meta_dict = {'geotransform': ds.GetGeoTransform(), 'projection': ds.GetProjection()}

    def load(self, img_path):
        img_name = self._get_img_name(img_path)
        if img_name != '':
            for n, c in self.chan_dict.items():
                self.load_band(c, f'{img_name}_{c}_{n}.tif')

    def create_original_img(self, b, r=1):
        arrays = [self.bands[self.chan_dict[c]].copy() for c in b]
        if len(arrays) == 1:
            arrays *= 3
        if len(arrays) == 2:
            arrays += [np.zeros_like(arrays[0])]
        assert len(arrays) == 3

        for i in range(3):
            arrays[i] -= arrays[i].mean()
            arrays[i] /= np.mean(arrays[i] ** 2)
            arrays[i][arrays[i] < -r] = -r
            arrays[i][arrays[i] > r] = r
        self.original_image = misc.toimage(np.array(arrays))
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

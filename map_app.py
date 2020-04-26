import tkinter as tk
from tkinter import ttk
import tkinter.filedialog as tk_filedialog

import os.path
from tkinter import messagebox

import numpy as np
from PIL import Image
import gdal

from histogram_dialog_window import HistogramDialogWindow
from utils import string_to_value, get_color, SATELLITE_CHANNELS, TabPolygonImage, plot_hist2d, load_proj, keycode2char

from segcanvas.wrappers import FocusLabelFrame


class MapWindow:
    def __init__(self, app):
        self.app = app
        self.root = app
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.title('SoilRegion (Map)')
        self.root.geometry("%dx%d%+d%+d" % (1200, 900, 100, 100))

        self.channels_img = ['07', '04', '02']
        self.channels_histogram = ['03', '04']
        self.steps = [300, 300]
        self.range = None
        self.n_regions = 5
        self.colors = np.array([[0, 0, 0], [255, 0, 0], [0, 255, 0], [0, 0, 255], [0, 255, 255], [255, 0, 255]])

        self._add_top_menu()
        self._add_canvas_frame()
        self.map_image = MapImage(self.colors)

        self.root.bind('<Shift_L>', self.on_shift)
        self.root.bind('<KeyRelease>', self.redraw)
        self.root.bind('<Control-KeyPress>', self._ctrl_callback)
        self.root.bind('<space>', self.mode_add_polygon)
        self.root.bind('<Escape>', self.mode_default)

    def _add_top_menu(self):
        self.top_menu = tk.Frame(self.root, height=60, bg='gray')
        self.top_menu.pack(side='top', fill='x')

        self.load_btn = tk.Button(self.top_menu, text='Load\nImage')
        self.save_btn = tk.Button(self.top_menu, text='Save\nImage')
        self.quit_btn = tk.Button(self.top_menu, text='Quit')
        self.mark_reg_btn = ttk.Button(self.top_menu, text='Mark region')
        self.upd_histogram_btn = ttk.Button(self.top_menu, text='Update')
        self.to_histogram_btn = tk.Button(self.top_menu, text='View\nHist')
        self.slider = tk.Scale(self.top_menu, from_=-3, to=3, resolution=.1, orient='horizontal',
                               command=self._delayed_reload_channels)
        self.slider.set(0)

        self.load_btn.bind("<Button-1>", self._load_file)
        self.save_btn.bind("<Button-1>", self.save_file)
        self.quit_btn.bind("<Button-1>", self.quit)
        self.mark_reg_btn.bind("<ButtonRelease-1>", self._mark_region)
        self.upd_histogram_btn.bind("<Button-1>", self._update_histogram_window)
        self.to_histogram_btn.bind("<Button-1>", self._open_histogram_dialog_window)

        self.load_btn.place(x=10, y=10, width=40, height=40)
        self.save_btn.place(x=60, y=10, width=40, height=40)
        self.quit_btn.place(x=110, y=10, width=40, height=40)
        self.mark_reg_btn.place(x=-120, y=10, relx=1, width=65, height=20)
        self.upd_histogram_btn.place(x=-120, y=30, relx=1, width=65, height=20)
        self.to_histogram_btn.place(x=-50, y=10, relx=1, width=40, height=40)
        self.slider.place(x=270, y=10)

        self.ch_stringvars = [tk.StringVar() for _ in range(3)]
        self.ch_entries = [tk.Entry(self.top_menu, textvariable=v) for v in self.ch_stringvars]
        for i, e in enumerate(self.ch_entries):
            e.place(x=160+30*i, y=10, width=25)
            e.delete(0, -1)
            e.insert(0, int(self.channels_img[i]))
            e.bind('<Return>', self.reload_channels)

        self.upd_histogram_btn.configure(state='disabled')

    def _add_canvas_frame(self):
        canvas_frame = FocusLabelFrame(self.root)
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        canvas = tk.Canvas(canvas_frame, highlightthickness=0, cursor="hand1", width=400, height=400)
        canvas.grid(row=0, column=0, sticky='nswe', padx=5, pady=5)
        canvas_frame.pack(side=tk.LEFT, fill="both", expand=True, padx=5, pady=5)
        self.canvas = canvas
        self.canvas_frame = canvas_frame
        self.canvas_image = MapTabImage(self.canvas_frame, self.canvas, self.root,
                                        Image.fromarray(np.zeros([80, 80, 3]), mode='RGB'), self.colors, 2)
        self.canvas_image.tab = 0

    def quit(self, _ev=None):
        if messagebox.askyesno(title="Quit?", message="Closing app may cause data loss."):
            self.root.destroy()

    def _mark_region(self, _ev=None):
        if str(self.upd_histogram_btn['state']) == 'normal':
            self.upd_histogram_btn.configure(state='disabled')
            self.root.after(100, self.mark_reg_btn.state, ['!pressed'])
            self.canvas_image.to_tab(0)
            self.redraw()
        else:
            self.upd_histogram_btn.configure(state='normal')
            self.root.after(100, self.mark_reg_btn.state, ['pressed'])
            self.canvas_image.to_tab(1)
            self.redraw()

    def _delayed_reload_channels(self, _ev):
        if not hasattr(self, '_job'):
            self._job = None
        if self._job:
            self.root.after_cancel(self._job)
        self._job = self.root.after(100, self.reload_channels)

    def reload_channels(self, _ev=None, channels=None):
        for i in range(3):
            if channels:
                self.channels_img[i] = channels[i]
            else:
                self.channels_img[i] = string_to_value(self.ch_stringvars[i].get()) or self.channels_img[i]
            self.ch_entries[i].delete(0, 'end')
            self.ch_entries[i].insert(0, int(self.channels_img[i]))
        if self.map_image.original_image is not None:
            self.map_image.create_original_img(self.channels_img, self.slider.get())
            self.canvas_image.reload_image(self.map_image.original_image, True)
            self.redraw()

    def _load_file(self, _ev):
        img_path = tk_filedialog.Open(self.root, filetypes=[('*.tif files', '*.tif')]).show()
        if isinstance(img_path, str) and img_path != '':
            if hasattr(self, 'histogram_window'):
                self.histogram_window.quit(None)
            if hasattr(self, 'histogram_dialog_window'):
                self.histogram_dialog_window.quit(None)
            self.map_image.load(img_path)
            self.img_name = self.map_image.img_name
            self.root.title(f'{self.img_name} - SoilRegion (Map)')
            self.reload_channels(channels=[self.map_image.chan_dict_rev[c] for c in ['swir2', 'nir', 'green']])
            self.map_image.create_original_img(self.channels_img, self.slider.get())
            self.canvas_image.reload_image(self.map_image.original_image, True)

    def save_file(self, _ev):
        fn = tk_filedialog.SaveAs(self.root, initialfile=f'{self.img_name}_mask.tif',
                                  filetypes=[('*.tif files', '*.tif')]).show()
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

    def on_shift(self, _arg):
        if self.map_image.original_image is not None:
            self.canvas_image.patch_image(self.map_image.original_image)

    def redraw(self, _arg=None):
        if self.canvas_image.tab == 0:
            if self.map_image.filtered_image is not None:
                self.canvas_image.patch_image(self.map_image.filtered_image)
            else:
                self.on_shift(None)
        else:
            self.canvas_image.patch_image(self.canvas_image.crafted_image)

    def mode_add_polygon(self, ev):
        return self.canvas_image.mode_add_polygon(ev)

    def mode_default(self, ev):
        return self.canvas_image.mode_default(ev)

    def add_histogram_window(self, histogram_window):
        self._add_histogram_window(histogram_window)

    def _add_histogram_window(self, histogram_window):
        self.histogram_window = histogram_window

    def _open_histogram_dialog_window(self, _arg):
        if hasattr(self, 'histogram_window'):
            if messagebox.askyesno(title="Close histogram window?",
                                   message="Closing histogram window may cause data loss."):
                self.histogram_window.quit(None)
            else:
                return
        if hasattr(self, 'histogram_dialog_window'):
            self.histogram_dialog_window.quit(None)

        self.histogram_dialog_window = HistogramDialogWindow(self)

    def _update_histogram_window(self, _ev):
        if not hasattr(self, 'histogram_window'):
            return
        mask = (self.canvas_image.rasters[self.canvas_image.tab] > 0)[:, ::-1].transpose()

        values = [self.map_image.bands[self.map_image.chan_dict[c]] * mask for c in self.channels_histogram]
        hist = np.histogram2d(values[0].flatten(), values[1].flatten(),
                              bins=self.steps, range=self.range)
        marked_hist_image = plot_hist2d(hist[0])
        self.histogram_window.canvas_image.patch_image(marked_hist_image)

    def _ctrl_callback(self, ev):
        if keycode2char(ev.keycode) == 's':
            self.save_file(None)
        if keycode2char(ev.keycode) == 'o':
            self._load_file(None)
        if keycode2char(ev.keycode) == 'enter':
            self._open_histogram_dialog_window(None)


class MapTabImage(TabPolygonImage):
    def _create_crafted_image(self, n):
        raster = self.rasters[n][:, ::-1]
        crafted_image_array = get_color(raster, self.colors)
        if n == 0:
            crafted_image_array = self.base_array
        else:
            mask = np.array([raster == 0] * 3).transpose([1, 2, 0])
            crafted_image_array = crafted_image_array * (1 - mask) + self.base_array * mask
        self.crafted_image = Image.fromarray(crafted_image_array.astype('uint8').transpose(1, 0, 2))


class MapImage:
    def __init__(self, colors):
        self.colors = colors
        self.bands = None
        self.mask = None
        self.original_image = None
        self.original_array = None
        self.filtered_image = None
        self.meta_dict = None
        self.img_name = None

    def load_band(self, b, img_path):
        if not os.path.isfile(img_path):
            return
        ds = gdal.Open(img_path)
        if ds is None:
            return
        band = ds.GetRasterBand(1)
        self.bands[b] = band.ReadAsArray()
        self.meta_dict = {'geotransform': ds.GetGeoTransform(), 'projection': ds.GetProjection()}

    def load(self, img_path):
        img_prefix = self._get_img_name(img_path)
        self.img_name = img_prefix.split('/')[-1]
        self.bands = dict()
        if img_prefix != '':
            for n, c in self.chan_dict.items():
                self.load_band(c, f'{img_prefix}_{c}_{n}.tif')

    def create_original_img(self, b, r=0):
        arrays = [self.bands[self.chan_dict[c]].copy() for c in b]
        if len(arrays) == 1:
            arrays *= 3
        if len(arrays) == 2:
            arrays += [np.zeros_like(arrays[0])]
        assert len(arrays) == 3

        for i in range(3):
            arrays[i] -= arrays[i].mean()
            arrays[i] /= np.mean(arrays[i] ** 2) ** .5
            bounds = np.quantile(arrays[i].flatten(), .01) * .99, np.quantile(arrays[i].flatten(), .99) * .99
            _arr = arrays[i][(bounds[0] < arrays[i]) * (arrays[i] < bounds[1])]
            rr = np.quantile(_arr, .05) / 2 ** r, np.quantile(_arr, .95) / 2 ** r
            arrays[i][arrays[i] < rr[0]] = rr[0]
            arrays[i][arrays[i] > rr[1]] = rr[1]
            arrays[i] -= arrays[i].mean()
            arrays[i] /= np.mean(arrays[i] ** 2) ** .5
            arrays[i] = ((arrays[i] - arrays[i].min()) / (arrays[i].max() - arrays[i].min()) * 255).astype('uint8')
            # arrays[i] = ((arrays[i] - rr[0]) / (rr[1] - rr[0]) * 255).astype('uint8')
        self.original_image = Image.fromarray(np.array(arrays).transpose([1, 2, 0]), mode='RGB')
        self.original_array = np.array(self.original_image)

    def create_filtered_image(self):
        arrays = [self.bands[self.chan_dict[c]] for c in self.mask.channels]

        types = self.mask.get_value(*tuple(arrays))
        colors = get_color(types, self.colors)
        filtered_image_array = (self.original_array * 0.5 + colors * 0.5).astype('uint8')
        self.filtered_image = Image.fromarray(filtered_image_array, mode='RGB')

    def _get_img_name(self, img_path):
        if not img_path.endswith('.tif'):
            return ''
        if img_path.split('_')[-4] not in SATELLITE_CHANNELS.keys():
            return ''
        self.satellite_type = img_path.split('_')[-4]
        self.chan_dict = SATELLITE_CHANNELS[self.satellite_type]
        self.chan_dict_rev = {v: k for k, v in self.chan_dict.items()}
        img_path = img_path[:-4]
        for n, c in self.chan_dict.items():
            if img_path.endswith(f'_{c}_{n}'):
                return img_path[:-2 - len(c) - len(n)]
        return ''


if __name__ == '__main__':
    load_proj()  # for exe file
    _app = tk.Tk()
    MapWindow(_app)
    _app.mainloop()

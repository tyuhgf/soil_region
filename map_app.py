import tkinter as tk
from functools import partial
from tkinter import ttk
import tkinter.filedialog as tk_filedialog

import os.path
from tkinter import messagebox

import numpy as np
from PIL import Image
import gdal

from histogram_dialog_window import HistogramDialogWindow
from utils import string_to_value, get_color, SATELLITE_CHANNELS, TabPolygonImage, load_proj, keycode2char, geometry_map

from segcanvas.wrappers import FocusLabelFrame


class MapWindow:
    def __init__(self, app):
        self.app = app
        self.root = app
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.title('SoilRegion (Map)')
        self.root.geometry("%dx%d%+d%+d" % geometry_map)

        self.channels_img = ['07', '04', '02']
        self.channels_histogram = ['03', '04']
        self.steps = [300, 300]
        self.range = None
        self.n_regions = 5
        self.colors = np.array([[0, 0, 0], [255, 0, 0], [0, 255, 0], [0, 0, 255], [0, 255, 255], [255, 0, 255]])

        self._add_top_menu()
        self._add_status_bar()
        self._add_canvas_frame()
        self.map_image = MapImage(self.colors)

        self.root.bind('<Shift_L>', self.on_shift)
        self.root.bind('<KeyRelease>', self.redraw)
        self.root.bind('<Control-KeyPress>', self._ctrl_callback)
        self.root.bind('<space>', self.mode_add_polygon)
        self.root.bind('<Escape>', self.mode_default)

    def _add_status_bar(self):
        self.status_bar = tk.Frame(self.root, height=15, bg='lightgray')
        self.status_bar.pack(side='bottom', fill='x')
        self.status_pos = tk.Label(self.status_bar, width=22, borderwidth=2, relief="groove")
        self.status_pos.pack(side='right')

    def _add_top_menu(self):
        self.top_menu = tk.Frame(self.root, height=60, bg='gray')
        self.top_menu.pack(side='top', fill='x')

        self.load_btn = tk.Button(self.top_menu, text='Load\nImage')
        self.save_btn = tk.Button(self.top_menu, text='Save\nImage')
        self.quit_btn = tk.Button(self.top_menu, text='Quit')
        self.mark_reg_btn = ttk.Button(self.top_menu, text='Poly')
        self.mask_btn = ttk.Button(self.top_menu, text='Mask')
        self.upd_histogram_btn = ttk.Button(self.top_menu, text='Show')
        self.to_histogram_btn = tk.Button(self.top_menu, text='View\nHist')
        self.slider = tk.Scale(self.top_menu, from_=-3, to=3, resolution=.1, orient='horizontal',
                               command=self._delayed_reload_channels)
        self.slider.set(0)

        self.load_btn.bind("<ButtonRelease-1>", self._load_file)
        self.save_btn.bind("<ButtonRelease-1>", self.save_file)
        self.quit_btn.bind("<ButtonRelease-1>", self.quit)
        self.mark_reg_btn.bind("<ButtonRelease-1>", self._mark_polygon)
        self.mask_btn.bind("<ButtonRelease-1>", self._mark_mask)
        self.upd_histogram_btn.bind("<ButtonRelease-1>", self._update_histogram_window)
        self.to_histogram_btn.bind("<ButtonRelease-1>", self._open_histogram_dialog_window)

        self.load_btn.place(x=10, y=10, width=40, height=40)
        self.save_btn.place(x=60, y=10, width=40, height=40)
        self.quit_btn.place(x=110, y=10, width=40, height=40)
        self.slider.place(x=270, y=10)
        self.to_histogram_btn.place(x=410, y=10, width=40, height=40)

        self.mark_reg_btn.place(x=-120, y=10, relx=1, width=40, height=40)
        self.mask_btn.place(x=-170, y=10, relx=1, width=40, height=40)
        self.upd_histogram_btn.place(x=-50, y=10, relx=1, width=40, height=40)

        self.ch_stringvars = [tk.StringVar() for _ in range(3)]
        self.ch_entries = [tk.Entry(self.top_menu, textvariable=v) for v in self.ch_stringvars]
        for i, e in enumerate(self.ch_entries):
            e.place(x=160+30*i, y=10, width=25)
            e.delete(0, -1)
            e.insert(0, int(self.channels_img[i]))
            e.bind('<Return>', self.reload_channels)

        self.upd_histogram_btn.configure(state='disabled')
        self.upd_histogram_btn_state = False
        self.polygon_or_mask_state = 'normal'
        self.map_mask = None

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
        self.canvas_image.canvas.bind('<Motion>', self._motion)
        self.canvas_image.tab = 0

    def quit(self, _ev=None):
        if messagebox.askyesno(title="Quit?", message="Closing app may cause data loss."):
            self.root.destroy()

    def _mark_mask(self, _ev=None):
        if self.map_mask is not None:
            self._configure_polygon_or_mask_state(
                'mask' if self.polygon_or_mask_state in ['normal', 'polygon'] else 'normal')

    def _mark_polygon(self, _ev=None):
        self._configure_polygon_or_mask_state(
            'polygon' if self.polygon_or_mask_state in ['normal', 'mask'] else 'normal')

    def mask_threshold_slider_destroy(self):
        if hasattr(self, 'mask_threshold_slider'):
            self.mask_threshold_slider.destroy()
            self.mask_threshold_entry.destroy()

    def _configure_polygon_or_mask_state(self, state='normal'):
        if state == 'polygon':
            self.polygon_or_mask_state = 'polygon'
            self.upd_histogram_btn.configure(state='normal')
            self._update_histogram_window(upd_histogram_btn_state=False)
            self.root.after(100, self.mark_reg_btn.state, ['pressed'])
            self.root.after(100, self.mask_btn.state, ['!pressed'])
            self.canvas_image.to_tab(1)
            self.mask_threshold_slider_destroy()
            self.redraw()
        elif state == 'normal':
            self.polygon_or_mask_state = 'normal'
            self._update_histogram_window(upd_histogram_btn_state=False)
            self.upd_histogram_btn.configure(state='disabled')
            self.root.after(100, self.mark_reg_btn.state, ['!pressed'])
            self.root.after(100, self.mask_btn.state, ['!pressed'])
            self.canvas_image.to_tab(0)
            self.mask_threshold_slider_destroy()
            self.redraw()
        else:  # state == 'mask'
            self.polygon_or_mask_state = 'mask'
            self.upd_histogram_btn.configure(state='normal')
            self._update_histogram_window(upd_histogram_btn_state=False)
            self.root.after(100, self.mark_reg_btn.state, ['!pressed'])
            self.root.after(100, self.mask_btn.state, ['pressed'])
            self.canvas_image.to_tab(0)

            l, r = self.map_mask.min(), self.map_mask.max()
            l, r = l - (r-l) * .1, r + (r-l) * .1
            self.mask_threshold_slider = tk.Scale(self.top_menu, from_=l, to=r, resolution=.01, orient='horizontal',
                                                  command=self._delayed_update_threshold)
            self.mask_threshold_slider.set((l+r)/2)
            self.mask_threshold_slider.place(x=-300, y=10, relx=1)
            self.mask_threshold_stringvar = tk.StringVar()
            self.mask_threshold_entry = tk.Entry(self.top_menu, textvariable=self.mask_threshold_stringvar)
            self.mask_threshold_entry.place(x=-360, y=10, relx=1, width=50)
            self.mask_threshold_entry.delete(0, -1)
            self.mask_threshold_entry.insert(0, 0)
            self.mask_threshold_entry.bind('<Return>', self.update_mask_threshold)

            self.update_mask_threshold(value=(l+r)/2)

            self.redraw()

    def _update_histogram_window(self, _ev=None, upd_histogram_btn_state=None):
        if isinstance(upd_histogram_btn_state, bool):
            self.upd_histogram_btn_state = upd_histogram_btn_state
        elif upd_histogram_btn_state is None:
            self.upd_histogram_btn_state = not self.upd_histogram_btn_state

        if self.upd_histogram_btn_state:
            self.root.after(100, self.upd_histogram_btn.state, ['pressed'])
        else:
            self.root.after(100, self.upd_histogram_btn.state, ['!pressed'])

        if not hasattr(self, 'histogram_window'):
            return
        if self.polygon_or_mask_state == 'normal' or not self.upd_histogram_btn_state:
            self.histogram_window.canvas_image.reload_image(self.histogram_window.base_image)
            self.histogram_window.canvas_image.to_tab(self.histogram_window.canvas_image.tab)
            return

        map_mask = None
        if self.polygon_or_mask_state == 'polygon':
            map_mask = (self.canvas_image.rasters[self.canvas_image.tab] > 0)[:, ::-1].transpose()
        elif self.polygon_or_mask_state == 'mask':
            map_mask = self.map_mask > self.mask_threshold_slider.get()

        base_array = np.array(self.histogram_window.base_image).transpose([1, 0, 2])
        values = self.map_image.get_bands(self.channels_histogram)
        values = [arr * map_mask for arr in values]
        hist = np.histogram2d(values[0][map_mask].flatten(), values[1][map_mask].flatten(),
                              bins=self.steps, range=self.range)
        hist = hist[0]
        mask = hist > 0
        mask = mask[:, ::-1]
        mask = np.array([mask] * 3, dtype=float).transpose([1, 2, 0])
        crafted_image_array = mask

        crafted_image_array = crafted_image_array * 256 * .5 + base_array * .5
        crafted_image = Image.fromarray(crafted_image_array.astype('uint8').transpose([1, 0, 2]))

        self.histogram_window.canvas_image.reload_image(crafted_image)
        self.histogram_window.canvas_image.to_tab(self.histogram_window.canvas_image.tab)
        # self.histogram_window.on_shift(None)

        self.redraw()

    def _delayed_reload_channels(self, _ev):
        if not hasattr(self, '_job'):
            self._job = None
        if self._job:
            self.root.after_cancel(self._job)
        self._job = self.root.after(100, self.reload_channels)

    def _delayed_update_threshold(self, _ev=None):
        if not hasattr(self, '_job'):
            self._job = None
        if self._job:
            self.root.after_cancel(self._job)

        job = partial(self.update_mask_threshold, value=self.mask_threshold_slider.get())
        job.__name__ = '_upd_mask_threshold'
        self._job = self.root.after(100, job)

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

    def update_mask_threshold(self, ev=None, value=None):
        value = value if value is not None else float(self.mask_threshold_entry.get()) if ev else None
        if value is not None:
            self.mask_threshold_slider.set(value)
            self.mask_threshold_entry.delete(0, 'end')
            self.mask_threshold_entry.insert(0, value)
        self._update_histogram_window(upd_histogram_btn_state='keep')
        self.redraw()

    def _load_file(self, _ev):
        img_path = tk_filedialog.Open(self.root, filetypes=[('*.tif files', '*.tif')]).show()
        if isinstance(img_path, str) and self.map_image.validate_img_path(img_path):
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
        elif isinstance(img_path, str) and img_path.endswith('.tif'):
            if not os.path.isfile(img_path):
                return
            ds = gdal.Open(img_path)
            if ds is None:
                return
            band = ds.GetRasterBand(1)
            self.map_mask = band.ReadAsArray()
            self.redraw()

    def save_file(self, _ev):
        fn = tk_filedialog.SaveAs(self.root, initialfile=f'{self.img_name}_mask.tif',
                                  filetypes=[('*.tif files', '*.tif')]).show()
        if fn == '':
            return
        if not fn.endswith('.tif'):
            fn += '.tif'
        arrays = self.map_image.get_bands(self.map_image.mask.channels)
        # todo revisit logic create_filtered_image
        types = self.map_image.mask.get_value(*tuple(arrays))

        driver = gdal.GetDriverByName("GTiff")
        outdata = driver.Create(fn, types.shape[1], types.shape[0], 1, gdal.GDT_UInt16)
        outdata.SetGeoTransform(self.map_image.meta_dict['geotransform'])
        outdata.SetProjection(self.map_image.meta_dict['projection'])
        outdata.GetRasterBand(1).WriteArray(types)
        outdata.FlushCache()  # saves to disk

    def on_shift(self, _ev):
        if self.map_image.original_image is not None:
            self.canvas_image.patch_image(self.map_image.original_image)

    def redraw(self, _ev=None):
        if self.polygon_or_mask_state == 'normal':
            img = self.map_image.filtered_image
        elif self.polygon_or_mask_state == 'polygon':
            img = self.canvas_image.crafted_image
        else:  # self.polygon_or_mask_state = 'mask'
            map_mask = np.array(self.map_mask > self.mask_threshold_slider.get(), dtype=int)
            colors = get_color(map_mask, self.colors)
            filtered_image_array = (self.map_image.original_array * 0.5 + colors * 0.5).astype('uint8')
            img = Image.fromarray(filtered_image_array, mode='RGB')

        if img is not None:
            self.canvas_image.patch_image(img)
        else:
            self.on_shift(None)

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

    def _ctrl_callback(self, ev):
        if keycode2char(ev.keycode) == 's':
            self.save_file(None)
        if keycode2char(ev.keycode) == 'o':
            self._load_file(None)
        if keycode2char(ev.keycode) == 'enter':
            self._open_histogram_dialog_window(None)

    def _motion(self, ev):
        if self.canvas_image.container:
            q = self.canvas_image.get_click_coordinates(ev)
            if q is not None:
                x, y = q
                self.status_pos['text'] = f'position: x={x} y={y}'


class MapTabImage(TabPolygonImage):
    def _left_mouse_button_pressed(self, event):
        if self.tab != 0:
            return super()._left_mouse_button_pressed(event)

    def _left_mouse_double_click(self, event):
        if self.tab != 0:
            return super()._left_mouse_double_click(event)

    def _left_mouse_button_released(self, event):
        if self.tab != 0:
            return super()._left_mouse_button_released(event)

    def _left_mouse_moving(self, event):
        if self.tab != 0:
            return super()._left_mouse_moving(event)

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
        self.bands[b] = band.ReadAsArray().astype(float)
        self.meta_dict = {'geotransform': ds.GetGeoTransform(), 'projection': ds.GetProjection()}

    def load(self, img_path):
        img_prefix = self._get_img_name(img_path)
        self.img_name = img_prefix.split('/')[-1]
        self.bands = dict()
        if img_prefix != '':
            for n, c in self.chan_dict.items():
                self.load_band(c, f'{img_prefix}_{c}_{n}.tif')

    def get_bands(self, channels, downsample=1):
        """downsample!=False will make all bands having shape of smallest // downsample."""
        arrays = [self.bands[self.chan_dict[c]].copy() for c in channels]

        if not downsample:
            return arrays

        shapes = np.array([a.shape for a in arrays])
        x = shapes[:, 0].min()
        y = shapes[:, 1].min()
        if not all(shapes[:, 0] % x == 0) or not all(shapes[:, 1] % y == 0):
            raise ValueError('Bands have incompatible shapes!')

        for i in range(len(arrays)):
            if not all(shapes[i] == [x, y]):
                arrays[i] = arrays[i][::shapes[i][0] // x][::shapes[i][1] // y]
        if downsample != 1:
            for i in range(len(arrays)):
                arrays[i] = arrays[i][::downsample, ::downsample]
        return arrays

    def create_original_img(self, b, r=0):
        arrays = self.get_bands(b)
        if len(arrays) == 1:
            arrays *= 3
        if len(arrays) == 2:
            arrays += [np.zeros_like(arrays[0])]
        assert len(arrays) == 3

        for i in range(len(arrays)):
            arr = arrays[i]

            low, high = np.quantile(arr.flatten(), .01), np.quantile(arr.flatten(), .99)
            low, high = low + (high-low) * .01, high - (high-low) * 0.01
            tmp_arr = arr[(low < arr) * (arr < high)]

            low, high, mean = np.quantile(tmp_arr, .05), np.quantile(tmp_arr, .95), tmp_arr.mean()
            low, high = mean + (low - mean) * 2 ** -r, mean + (high - mean) * 2 ** -r
            arr[arr < low] = low
            arr[arr > high] = high

            arrays[i] = ((arr - arr.min()) / (arr.max() - arr.min()) * 255).astype('uint8')
        self.original_image = Image.fromarray(np.array(arrays).transpose([1, 2, 0]), mode='RGB')
        self.original_array = np.array(self.original_image)

    def create_filtered_image(self):
        arrays = self.get_bands(self.mask.channels)

        types = self.mask.get_value(*tuple(arrays))
        colors = get_color(types, self.colors)
        filtered_image_array = (self.original_array * 0.5 + colors * 0.5).astype('uint8')
        self.filtered_image = Image.fromarray(filtered_image_array, mode='RGB')

    def _get_img_name(self, img_path):
        if not self.validate_img_path(img_path):
            return ''
        self.satellite_type = img_path.split('_')[-4]
        self.chan_dict = SATELLITE_CHANNELS[self.satellite_type]
        self.chan_dict_rev = {v: k for k, v in self.chan_dict.items()}
        img_path = img_path[:-4]
        for n, c in self.chan_dict.items():
            if img_path.endswith(f'_{c}_{n}'):
                return img_path[:-2 - len(c) - len(n)]
        return ''

    @staticmethod
    def validate_img_path(img_path):
        if not img_path.endswith('.tif'):
            return False
        img_path = img_path[:-4]
        if len(img_path.split('_')) < 5 or img_path.split('_')[-4] not in SATELLITE_CHANNELS.keys():
            return False
        if img_path.split('_')[-1] not in SATELLITE_CHANNELS[img_path.split('_')[-4]].keys():
            return False
        return True


if __name__ == '__main__':
    load_proj()  # for exe file
    _app = tk.Tk()
    MapWindow(_app)
    _app.mainloop()

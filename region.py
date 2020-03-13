import json
import tkinter as tk
from tkinter import ttk
import tkinter.filedialog as tk_filedialog

from utils import RegionImage, NamedFrame, N_REGIONS, plot_hist

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

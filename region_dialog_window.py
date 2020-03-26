import tkinter as tk
import numpy as np
from PIL.ImageTk import PhotoImage

from region import RegionWindow
from segcanvas.canvas import CanvasImage
from segcanvas.wrappers import FocusLabelFrame
from utils import string_to_value, plot_hist2d, plot_hist


class RegionDialogWindow:
    def __init__(self, map_window):
        self.map_window = map_window
        self.map_image = map_window.map_image
        self.app = map_window.app
        self.root = tk.Toplevel(self.app)
        self.root.title('Preview')
        self.root.geometry("%dx%d%+d%+d" % (1200, 900, 500, 100))

        self.channels_region = [self.map_window.map_image.chan_dict_rev[c] for c in ['red', 'nir']]
        self.steps = [100, 100]

        self.graph_x_img = None
        self.graph_y_img = None

        self._add_top_menu()
        self._calc_ranges()
        self._add_left_menu()
        self._add_preview()
        self._reload_hist()

    def _add_top_menu(self):
        self.top_menu = tk.Frame(self.root, height=60, bg='gray')
        self.top_menu.pack(side='top', fill='x')

        self.to_region_btn = tk.Button(self.top_menu, text='OK')
        self.to_region_btn.bind("<Button-1>", self.open_region_window)

        self.to_region_btn.place(x=-50, y=10, relx=1, width=40, height=40)

        self.ch_stringvars = [tk.StringVar() for _ in range(2)]
        self.ch_entries = [tk.Entry(self.top_menu, textvariable=v) for v in self.ch_stringvars]
        self.ch_labels = [tk.Label(self.top_menu, bg='gray', text='ch' + str(i + 1), font=("Arial", 8)) for i in
                          range(2)]
        for i, (e, l) in enumerate(zip(self.ch_entries, self.ch_labels)):
            l.place(x=10 + 30 * i, y=10, width=25, height=10)
            e.place(x=10 + 30 * i, y=22, width=25)
            e.delete(0, -1)
            e.insert(0, int(self.channels_region[i]))
            e.bind('<Return>', self.reload_graphs)

        self.steps_stringvars = [tk.StringVar() for _ in range(2)]
        self.steps_entries = [tk.Entry(self.top_menu, textvariable=v) for v in self.steps_stringvars]
        self.steps_labels = [tk.Label(self.top_menu, bg='gray', text='steps' + str(i + 1),
                                      font=("Arial", 8)) for i in range(2)]
        for i, (e, l) in enumerate(zip(self.steps_entries, self.steps_labels)):
            l.place(x=100 + 40 * i, y=10, width=35, height=10)
            e.place(x=100 + 40 * i, y=22, width=35)
            e.delete(0, -1)
            e.insert(0, self.steps[i])
            e.bind('<Return>', self.reload_graphs)

    def _calc_ranges(self, _ev=None):
        values = [self.map_image.bands[self.map_image.chan_dict[c]].copy() for c in self.channels_region]
        self.x_range, self.y_range = ([values[i].min(), values[i].max()] for i in range(2))

        for i in range(2):
            values[i][values[i] < values[i].min() + 0.00000001] = np.nan
        self.graphs = [plot_hist(values[i]) for i in range(2)]

    def _add_left_menu(self):
        self.left_menu = tk.Frame(self.root, width=400, bg='red')
        self.left_menu.pack(side='left', fill='y')

        labels = ['x_min', 'x_max']
        self.xrange_stringvars = [tk.StringVar() for _ in range(2)]
        self.xrange_entries = [tk.Entry(self.left_menu, textvariable=v) for v in self.xrange_stringvars]
        self.xrange_labels = [tk.Label(self.left_menu, bg='gray', text=labels[i],
                                       font=("Arial", 8)) for i in range(2)]
        for i, (e, l) in enumerate(zip(self.xrange_entries, self.xrange_labels)):
            l.place(x=10 + 65 * i, y=300, width=60, height=10)
            e.place(x=10 + 65 * i, y=312, width=60)
            e.delete(0, -1)
            e.insert(0, self.x_range[i])
            e.bind('<Return>', self._reload_hist)

        labels = ['y_min', 'y_max']
        self.yrange_stringvars = [tk.StringVar() for _ in range(2)]
        self.yrange_entries = [tk.Entry(self.left_menu, textvariable=v) for v in self.yrange_stringvars]
        self.yrange_labels = [tk.Label(self.left_menu, bg='gray', text=labels[i],
                                       font=("Arial", 8)) for i in range(2)]
        for i, (e, l) in enumerate(zip(self.yrange_entries, self.yrange_labels)):
            l.place(x=10 + 65 * i, y=700, width=60, height=10)
            e.place(x=10 + 65 * i, y=712, width=60)
            e.delete(0, -1)
            e.insert(0, self.y_range[i])
            e.bind('<Return>', self._reload_hist)

        self.graph_x_img = PhotoImage(self.graphs[0], master=self.left_menu)
        self.graph_y_img = PhotoImage(self.graphs[1], master=self.left_menu)
        self.graph_x_frame = tk.Label(self.left_menu, image=self.graph_x_img)
        self.graph_y_frame = tk.Label(self.left_menu, image=self.graph_y_img)
        self.graph_x_frame.place(x=10, y=10)
        self.graph_y_frame.place(x=10, y=410)

    def _add_preview(self, _ev=None):
        canvas_frame = FocusLabelFrame(self.root)
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        canvas = tk.Canvas(canvas_frame, highlightthickness=0, cursor="hand1", width=1000, height=1000)
        canvas.grid(row=0, column=0, sticky='nswe', padx=5, pady=5)
        canvas_frame.pack(side=tk.LEFT, fill="both", expand=True, padx=5, pady=5)
        self.canvas = canvas
        self.canvas_frame = canvas_frame
        self.canvas_image = CanvasImage(self.canvas_frame, self.canvas)

    def _reload_hist(self, _ev=None):
        for i in range(2):
            self.x_range[i] = string_to_value(self.xrange_entries[i].get(), 'float') or self.x_range[i]
            self.xrange_entries[i].delete(0, 'end')
            self.xrange_entries[i].insert(0, self.x_range[i])
        for i in range(2):
            self.y_range[i] = string_to_value(self.yrange_entries[i].get(), 'float') or self.y_range[i]
            self.yrange_entries[i].delete(0, 'end')
            self.yrange_entries[i].insert(0, self.y_range[i])
        for i in range(2):
            self.steps[i] = string_to_value(self.steps_entries[i].get(), 'int') or self.steps[i]
            self.steps_entries[i].delete(0, 'end')
            self.steps_entries[i].insert(0, self.steps[i])

        values = [self.map_image.bands[self.map_image.chan_dict[c]] for c in self.channels_region]
        self.hist = np.histogram2d(values[0].flatten(), values[1].flatten(),
                                   bins=self.steps,
                                   range=[self.x_range, self.y_range])

        self.base_image = plot_hist2d(self.hist[0])

        self.canvas_image.reload_image(self.base_image)

    def reload_graphs(self, _ev):
        for i in range(2):
            self.steps[i] = string_to_value(self.steps_entries[i].get(), 'int') or self.steps[i]
            self.steps_entries[i].delete(0, 'end')
            self.steps_entries[i].insert(0, self.steps[i])
        for i in range(2):
            self.channels_region[i] = string_to_value(self.ch_entries[i].get(), 'int_to_str') or self.channels_region[i]
            self.ch_entries[i].delete(0, 'end')
            self.ch_entries[i].insert(0, int(self.channels_region[i]))

        self._calc_ranges()
        self._reload_hist()

        self.graph_x_img = PhotoImage(self.graphs[0], master=self.left_menu)
        self.graph_y_img = PhotoImage(self.graphs[1], master=self.left_menu)
        self.graph_x_frame['image'] = self.graph_x_img
        self.graph_y_frame['image'] = self.graph_y_img

    def open_region_window(self, _ev):
        self.map_window.channels_region = self.channels_region
        self.map_window.region_window = RegionWindow(self.map_window, self.hist, self.base_image)
        self.quit()

    def quit(self, _ev=None):
        self.root.destroy()

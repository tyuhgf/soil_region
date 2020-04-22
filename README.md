# soil_region
Tkinter app for satellite image manipulation

### Input files format
Channels should be `.tif` files with same prefix and suffixes

. `_blue_01`, `_green_02`, `_red_03`, `_nir_04`, `_swir1_05`, `_swir2_07`
for Landsat5 and Landsat7 (`LT05` or `LE07` in filename)

. `_blue_02`, `_green_03`, `_red_04`, `_nir_05`, `_swir1_06`, `_swir2_07`
for Landsat8 (`LC08` in filename).

Missed channels do not cause any exception but should not be used subsequently.

### Preview window
Histograms and values are updated on `return` key in number fields.

### Region window
On color tabs `space` key switches to add polygon mode (mouse click adds
a vertex to a polygon). Exit to default mode can be done by `esc` key or
tab change. In default mode polygons can be changed by mouse moves.
Double click on vertex deletes a vertex, double click on edge center
deletes the whole polygon.

## Make exe
```pyi-makespec --onefile map_app.py```

```
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_data_files
import sys
 datas=[(os.path.join(os.path.split(sys.executable)[0], 'Library/bin/gdal*.dll'), 'gdal')] +
    collect_data_files('scipy') +
    [(os.path.join(os.path.split(sys.executable)[0], 'Library/share/proj/*'), 'proj')],
 hiddenimports=collect_submodules('scipy'),
```

```pyinstaller map_app.spec```

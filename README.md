# Static WMTS on GitHub

This repository allows you to turn your georeferences data into a static WMTS service.

You can use it in two ways:

* By forking this repository and setting your static WMTS service using the GitHub
* By cloning this repository, using the `process.py` to create a static WMTS service content and publishing it using a web server of your choice

## On GitHub

* Fork this repository.
* Adjust the repository settings allowing GitHub Actions to push changes back to it.
  Go to https://github.com/{your repo}/settings/actions and in the **Workflow permissions** section choose the **Read and write permissions**.
* Adjust content of:
  * `wmts.xml` - provide metadata about your WMTS service (to be honest things will work also without that but it is a good practice to provide some metadata)
  * `sources.csv` - provide a list of raster sources you want to publish with some basic metadata about them
* Commit and push the changes to the GitHub.
  This will automatically trigger preprocessing of the data specified in the `sources.csv`.
* Set up GitHub pages for your repository.
  Go to https://github.com/{your repo}/settings/pages and set publishing from branch **publish** and directory **docs**.
* Congratulations, you can now:
  * Get the WMTS `get capabilities` response at https://{your organization}.github.io/{your repo}/GetCapabilities.xml
  * Access the XYZ tiles at https://{your organization}.github.io/{your repo}/{source id}/{zoom level}/{x}/{y}.png
    e.g. to show a sample raster defined in this repo

## On your own web server

* Clone this repository
* Adjust content of: 
  * `wmts.xml` - provide metadata about your WMTS service (to be honest things will work also without that but it is a good practice to provide some metadata)
  * `sources.csv` - provide a list of raster sources you want to publish with some basic metadata about them
    (you can use file paths as the `url` as well)
* Install [gdal](https://gdal.org/en/stable/) scripts, e.g. in Ubuntu/Debian `apt install gdal-bin`.
* Run `python3 process.py baseUrlOfYourWebServer`.
* Copy the contents of the `docs` folder to your web server.
* Congratulations, you can now:
  * Get the WMTS `get capabilities` response at {your webserver base URL}/GetCapabilities.xml
  * Access the XYZ tiles at {your webserver base URL}/{source id}/{zoom level}/{x}/{y}.png

## Examples

See the `leafletSample.html` for an example using the [Leaflet](https://leafletjs.com) library and this repository.

## FAQ

* Why `sources.csv` expects URL? Why I can not just put the raster in the repository?  
  Well, you can. The `url` column of the `sources.csv` can be also a path to a raster file.
  The problem is the GitHub limits single file size to 50 MB rasters you want to publish will be likely (much) larger than that.
  Using URL allows to overcome this limitation but yeah, it means you must, at least temporarily, publish your raster in a way it can be fetched with an URL.
* Why my raster is not displayed at a high zoom levels?  
  Because the WMTS/XYZ tiles library you are using is dumb and does not honor the information about the maximum zoom level included in the WMTS get capabilities response ☹️. (or most probably does not even try to retrieve this information in the first place).
  The `process.py` script creates tiles only up to the `ceiling(zoom level derived from the original image resolution)` as creating tiles on higher zoom level is just a waste of time and disk space.
  If this is the case, then you can check what is the maximum zoom level of a given source either by looking at the content of the `docs/{source id}` directory or at the `docs/GetCapabilities.xml` file and checking for the `<TileMatrixSet> <ows:Identifier>WebMercatorQuad{maxZoomLevel} (...)` of a given layer and knowing that, set up your XYZ tiles display library to honor this limit by hand.
  * This issue affects a very popular [Leaflet](https://leafletjs.com) library.
* How to add more sources?  
  Just add them to the `sources.csv`, commit and push.
* How ro remove sources?
  Just remove them from the `sources.csv`, commit and push.

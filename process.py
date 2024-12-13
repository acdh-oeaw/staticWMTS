from csv import DictReader
from json import dump, load
from logging import basicConfig, info, warning, error, INFO
from math import ceil, log
from os import listdir, makedirs, unlink
from os.path import isdir, join, exists
from osgeo import gdal
from osgeo.ogr import Geometry, wkbPoint
from osgeo.osr import SpatialReference, CoordinateTransformation
from requests import get
from shutil import rmtree
from subprocess import check_call
from sys import argv, stdout
from tempfile import gettempdir
from xml.dom.minidom import parse

basicConfig(stream=stdout, format="%(levelname)s:%(asctime)s:%(message)s", encoding='utf-8', level=INFO)

dataDir = 'docs' # for github pages compatibility
makedirs(dataDir, 0o755, True)

gdal.UseExceptions()
tmpdir = gettempdir()
proj3857 = SpatialReference()
proj3857.ImportFromEPSG(3857)
proj4326 = SpatialReference()
proj4326.ImportFromEPSG(4326)
trans3857to4326 = CoordinateTransformation(proj3857, proj4326)

sources = []
with open('sources.csv', newline='') as fcsv:
    for source in DictReader(fcsv):
        try:
            pdata = join(dataDir, source['id'])
            pmeta = join(pdata, 'meta.json')
            # prepare tiles
            if not exists(pdata):
                info(f"Preprocessing {source['id']}")
                # download the source file
                if source['url'].startswith('http'):
                    info(f"    downloading {source['url']}")
                    resp = get(source['url'], stream=True)
                    pdwnl = join(tmpdir, 'src')
                    with open(pdwnl, 'wb') as ftmp:
                        for chunk in resp.iter_content(chunk_size=1048576):
                            ftmp.write(chunk)
                else:
                    pdwnl = source['url']
                # reproject to EPSG:3857 and compute the max zoom
                info(f"    reprojecting to EPSG:3857")
                p3857 = join(tmpdir, '3857.tif')
                gdal.Warp(p3857, pdwnl, dstSRS='EPSG:3857')
                rast = gdal.Open(p3857)
                trans  = rast.GetGeoTransform()
                del rast
                res = max(abs(trans[1]), abs(trans[5]))
                zoomMax = ceil(log(156543.03 / res, 2))
                resMax = 156543.03 / 2**zoomMax
                # reproject to EPSG:3857 at the max zoom and tile
                info(f"    tiling up to zoom level {zoomMax}")
                gdal.Warp(p3857, pdwnl, dstSRS='EPSG:3857', resampleAlg='bilinear', xRes=resMax, yRes=resMax, format='GTiff')
                makedirs(pdata, 0o755, True)
                cmd = ["/usr/bin/gdal2tiles.py", "--xyz", f"-z 1-{zoomMax}", "--processes=4", "--tilesize=256", p3857, pdata]
                check_call(cmd)
                # write metadata required to produce WMTS GetCapabilities
                info(f"    computing metadata")
                rast = gdal.Open(p3857)
                trans  = rast.GetGeoTransform()
                dim = (rast.RasterXSize, rast.RasterYSize)
                del rast
                lower = Geometry(wkbPoint)
                lower.AddPoint(trans[0]                    , trans[3] + trans[5] * dim[1])
                upper = Geometry(wkbPoint)
                upper.AddPoint(trans[0] + trans[1] * dim[0], trans[3])
                upper.Transform(trans3857to4326)
                upper = upper.GetPoint()
                lower.Transform(trans3857to4326)
                lower = lower.GetPoint()
                source['lower'] = f"{lower[1]} {lower[0]}"
                source['upper'] = f"{upper[1]} {upper[0]}"
                source['zoomMax'] = zoomMax
                with open(pmeta, 'w') as fmeta:
                    dump(source, fmeta, indent=4)
                # cleanup
                unlink(p3857)
                unlink(pdwnl)

            info(f"Reading metadata for {source['id']}")
            with open(pmeta, 'rb') as fmeta:
                meta = load(fmeta)
            sources.append(meta)
        except Exception as e:
            error(f"{e}")
            if exists(pdata):
                rmtree(pdata, True)

# remove old data
ids = set([x['id'] for x in sources])
for i in listdir(dataDir):
    pdir = join(dataDir, i)
    if isdir(pdir) and i not in ids:
        info(f'Removing {pdir}')
        rmtree(pdir, True)

# prepare GetCapabilities.xml
info("Generating GetCapabilities.xml")
baseUrl = argv[1]
if baseUrl[-1] != '/':
    baseUrl = baseUrl + '/'
with open('wmts.xml', 'r') as f:
    gcxml = parse(f)
gcxml.getElementsByTagNameNS('http://www.opengis.net/wmts/1.0', 'ServiceMetadataURL')[0].setAttributeNS('http://www.w3.org/1999/xlink', 'xlink:href', baseUrl + 'GetCapabilities.xml')
for i in gcxml.getElementsByTagNameNS('http://www.opengis.net/ows/1.1', 'Get'):
    i.setAttributeNS('http://www.w3.org/1999/xlink', 'xlink:href', baseUrl)
layers = gcxml.getElementsByTagNameNS('http://www.opengis.net/wmts/1.0', 'Contents')[0]
layer = gcxml.getElementsByTagNameNS('http://www.opengis.net/wmts/1.0', 'Layer')[0]
layers.removeChild(layer)
matrixsets = set()
for i in sources:
    info(f"    including {i['id']}: {i['title']}")
    matrixsets.add(i['zoomMax'])
    l = layer.cloneNode(True)
    l.getElementsByTagNameNS('http://www.opengis.net/ows/1.1', 'Title')[0].firstChild.nodeValue = i['title']
    l.getElementsByTagNameNS('http://www.opengis.net/ows/1.1', 'Identifier')[0].firstChild.nodeValue = i['id']
    l.getElementsByTagNameNS('http://www.opengis.net/wmts/1.0', 'ResourceURL')[0].setAttributeNS('http://www.opengis.net/wmts/1.0', 'template', baseUrl + i['id'] + "/{TileMatrix}/{TileCol}/{TileRow}.png")
    l.getElementsByTagNameNS('http://www.opengis.net/wmts/1.0', 'TileMatrixSet')[0].firstChild.nodeValue = f"WebMercatorQuad{i['zoomMax']}"
    l.getElementsByTagNameNS('http://www.opengis.net/ows/1.1', 'LowerCorner')[0].firstChild.nodeValue = i['lower']
    l.getElementsByTagNameNS('http://www.opengis.net/ows/1.1', 'UpperCorner')[0].firstChild.nodeValue = i['upper']
    l.getElementsByTagNameNS('http://www.opengis.net/ows/1.1', 'Abstract')[0].firstChild.nodeValue = i['abstract']
    if i['keywords'] != '':
        keywords = l.getElementsByTagNameNS('http://www.opengis.net/ows/1.1', 'Keywords')[0]
        for kw in i['keywords'].split(','):
            tmp = gcxml.createElementNS('http://www.opengis.net/ows/1.1', 'Keyword')
            tmp.appendChild(gcxml.createTextNode(kw))
            keywords.appendChild(tmp)
    layers.appendChild(l)
matrixset = gcxml.getElementsByTagNameNS('http://www.opengis.net/wmts/1.0', 'TileMatrixSet')[0]
layers.removeChild(matrixset)
matrix = matrixset.getElementsByTagNameNS('http://www.opengis.net/wmts/1.0', 'TileMatrix')[0]
matrixset.removeChild(matrix)
for zoomMax in matrixsets:
    info(f"    generating TileMatrixSet for maximum zoom level {zoomMax}")
    ms = matrixset.cloneNode(True)
    ms.getElementsByTagNameNS('http://www.opengis.net/ows/1.1', 'Identifier')[0].firstChild.nodeValue = f"WebMercatorQuad{zoomMax}"
    z = 1
    z2 = 4
    denom = 559082264.028717 / 2
    while z <= zoomMax:
        m = matrix.cloneNode(True)
        m.getElementsByTagNameNS('http://www.opengis.net/ows/1.1', 'Identifier')[0].firstChild.nodeValue = str(z)
        m.getElementsByTagNameNS('http://www.opengis.net/wmts/1.0', 'ScaleDenominator')[0].firstChild.nodeValue = str(denom)
        m.getElementsByTagNameNS('http://www.opengis.net/wmts/1.0', 'MatrixWidth')[0].firstChild.nodeValue = str(z2)
        m.getElementsByTagNameNS('http://www.opengis.net/wmts/1.0', 'MatrixHeight')[0].firstChild.nodeValue = str(z2)
        z = z + 1
        z2 = z2 * 2
        denom = denom / 2
        ms.appendChild(m)
    layers.appendChild(ms)

with open(join(dataDir, 'GetCapabilities.xml'), 'w') as f:
    gcxml.writexml(f)
info("Finished")

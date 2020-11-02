#!/usr/bin/env python3

import vincenty as v
import numpy as np
import math
import time
import sqlite3
from optparse import OptionParser
from os import system, name
from lxml import etree
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from geojson import Point, MultiPoint, Feature, FeatureCollection

d = 40000 #meters

all_pt_style = {"name": "Various Points", "marker-color": "#FF0000"}
best_pt_style = {"name": "Most Likely TX Location", "marker-color": "#00FF00"}

class receiver:
    def __init__(self, station_url):
        self.station_url = station_url
        try:
            self.update()
        except:
            print("Problem connecting to receiver.")
            quit()

    def update(self):
        try:
            xml_contents = etree.parse(self.station_url)
            xml_station_id = xml_contents.find('STATION_ID')
            self.station_id = xml_station_id.text
            xml_doa_time = xml_contents.find('TIME')
            self.doa_time = int(xml_doa_time.text)
            xml_freq = xml_contents.find('FREQUENCY')
            self.frequency = float(xml_freq.text)
            xml_latitude = xml_contents.find('LOCATION/LATITUDE')
            self.latitude = float(xml_latitude.text)
            xml_longitude = xml_contents.find('LOCATION/LONGITUDE')
            self.longitude = float(xml_longitude.text)
            xml_heading = xml_contents.find('LOCATION/HEADING')
            self.heading = float(xml_heading.text)
            xml_doa = xml_contents.find('DOA')
            self.raw_doa = float(xml_doa.text)
            self.doa = self.heading + (360 - self.raw_doa)
            if self.doa < 0:
                self.doa += 360
            elif self.doa > 359:
                self.doa -= 360
            xml_power = xml_contents.find('PWR')
            self.power = float(xml_power.text)
            xml_conf = xml_contents.find('CONF')
            self.confidence = int(xml_conf.text)
        except:
            print("Problem connecting to receiver.")
            pass

    latitude = 0.0
    longitude = 0.0
    heading = 0.0
    raw_doa = 0.0
    doa = 0.0
    frequency = 0.0
    power = 0.0
    confidence = 0
    doa_time = 0


def plot_polar(lat_a, lon_a, lat_a2, lon_a2):
    # Convert points in great circle 1, degrees to radians
    p1_lat1_rad = math.radians(lat_a)
    p1_long1_rad =  math.radians(lon_a)
    p1_lat2_rad =  math.radians(lat_a2)
    p1_long2_rad =  math.radians(lon_a2)

    # Put in polar coordinates
    x1 = math.cos(p1_lat1_rad) * math.cos(p1_long1_rad)
    y1 = math.cos(p1_lat1_rad) * math.sin(p1_long1_rad)
    z1 = math.sin(p1_lat1_rad)
    x2 = math.cos(p1_lat2_rad) * math.cos(p1_long2_rad)
    y2 = math.cos(p1_lat2_rad) * math.sin(p1_long2_rad)
    z2 = math.sin(p1_lat2_rad)

    return ([x1, y1, z1], [x2, y2, z2])

# Find line of intersection between two planes
# L = np.cross(N1, N2)
def plot_intersects(lat_a, lon_a, doa_a, lat_b, lon_b, doa_b, max_distance = 50000):
    # plot another point on the lob
    # v.direct(lat_a, lon_a, doa_a, d)
    # returns (lat_a2, lon_a2)

    # Get normal to planes containing great circles
    # np.cross product of vector to each point from the origin
    coord_a2 = v.direct(lat_a, lon_a, doa_a, d)
    coord_b2 = v.direct(lat_b, lon_b, doa_b, d)
    plane_a = plot_polar(lat_a, lon_a, *coord_a2)
    plane_b = plot_polar(lat_b, lon_b, *coord_b2)
    N1 = np.cross(plane_a[0], plane_a[1])
    N2 = np.cross(plane_b[0], plane_b[1])

    # Find line of intersection between two planes
    L = np.cross(N1, N2)
    # Find two intersection points
    X1 = L / np.sqrt(L[0]**2 + L[1]**2 + L[2]**2)
    X2 = -X1
    mag = lambda q: np.sqrt(np.vdot(q, q))
    dist1 = mag(X1-plane_a[0])
    dist2 = mag(X2-plane_a[0])
    #return the (lon_lat pair of the closer intersection)
    if dist1 < dist2:
        i_lat = math.asin(X1[2]) * 180./np.pi
        i_long = math.atan2(X1[1], X1[0]) * 180./np.pi
    else:
        i_lat = math.asin(X2[2]) * 180./np.pi
        i_long = math.atan2(X2[1], X2[0]) * 180./np.pi

    check_bearing = v.get_heading((lat_a, lon_a), (i_lat, i_long))

    if abs(check_bearing - doa_a) < 5:
        km = v.inverse([lat_a, lon_a], [i_lat, i_long])
        if km[0] < max_distance:
            return (i_lat, i_long)
        else:
            return None

def process_data(database_name, outfile, eps, min_samp):
    conn = sqlite3.connect(database_name)
    c = conn.cursor()

    intersect_list = []

    c.execute("SELECT COUNT(*) FROM intersects")
    n_intersects = int(c.fetchone()[0])
    #print(n_intersects)
    c.execute("SELECT latitude, longitude FROM intersects")
    intersect_array = np.array(c.fetchall())
    # print(intersect_array)
    likely_location = []
    best_point = []
    if intersect_array.size != 0:
        if eps > 0:
            X = StandardScaler().fit_transform(intersect_array)

            # Compute DBSCAN
            db = DBSCAN(eps=eps, min_samples=min_samp).fit(X)
            core_samples_mask = np.zeros_like(db.labels_, dtype=bool)
            core_samples_mask[db.core_sample_indices_] = True
            labels = db.labels_

            intersect_array = np.column_stack((intersect_array, labels))
            # print(intersect_array)

            # Number of clusters in labels, ignoring noise if present.
            n_clusters_ = len(set(labels)) - (1 if -1 in labels else 0)
            n_noise_ = list(labels).count(-1)
            clear()
            print('Number of clusters: %d' % n_clusters_)
            print('Outliers Removed: %d' % n_noise_)
            # print(intersect_array)

            for x in range(n_clusters_):
                cluster = np.array([]).reshape(0,2)
                for y in range(len(intersect_array)):
                    if intersect_array[y][2] == x:
                        cluster = np.concatenate((cluster, [intersect_array[y][0:2]]), axis = 0)
                likely_location.append(Reverse(np.mean(cluster, axis=0).tolist()))
                best_point = Feature(properties = best_pt_style, geometry = MultiPoint(tuple(likely_location)))

            for x in likely_location:
                print(Reverse(x))

        for x in intersect_array:
            try:
                if x[2] >= 0:
                    intersect_list.append(Reverse(x[0:2].tolist()))
            except IndexError:
                intersect_list.append(Reverse(x.tolist()))
        #print(intersect_list)
        all_the_points = Feature(properties = all_pt_style, geometry = MultiPoint(tuple(intersect_list)))

        with open(outfile, "w") as file1:
            if eps > 0:
                file1.write(str(FeatureCollection([best_point, all_the_points])))
            else:
                file1.write(str(FeatureCollection([all_the_points])))
        print(f"Wrote file {geofile}")

    else:
        print("No Intersections.")

def Reverse(lst):
    lst.reverse()
    return lst

def clear():
      # for windows
    if name == 'nt':
        _ = system('cls')
    # for mac and linux(here, os.name is 'posix')
    else:
        _ = system('clear')

if __name__ == '__main__':
    usage = "usage: %prog [options]"
    parser = OptionParser(usage=usage)
    parser.add_option("-g", "--geofile", dest="geofile", help="GeoJSON Output File", metavar="FILE")
    parser.add_option("-r", "--receivers", dest="rx_file", help="List of receiver URLs", metavar="FILE")
    parser.add_option("-d", "--database", dest="database_name", help="Database File", metavar="FILE")
    parser.add_option("-e", "--epsilon", dest="eps", help="Max Clustering Distance, Default 0.2. 0 to disable clustering.",
    metavar="Number", type="float", default=0.2)
    parser.add_option("-c", "--confidence", dest="conf", help="Minimum confidence value, default 10",
    metavar="Number", type="int", default=10)
    parser.add_option("-p", "--power", dest="pwr", help="Minimum power value, default 10",
    metavar="Number", type="int", default=10)
    parser.add_option("-m", "--min-samples", dest="minsamp", help="Minimum samples per cluster. Default 20",
    metavar="Number", type="int", default=20)
    parser.add_option("--dist-from-reference", dest="mdfr", help="Max distance in km from intersection with strongest signal.",
    metavar="Number", type="int", default=500)
    (options, args) = parser.parse_args()

    mandatories = ['geofile', 'rx_file', 'database_name']
    for m in mandatories:
      if options.__dict__[m] is None:
        print("You forgot an arguement")
        parser.print_help()
        exit(-1)

    geofile = options.geofile
    rx_file = options.rx_file
    database_name = options.database_name
    eps = options.eps
    min_conf = options.conf
    min_power = options.pwr
    max_dist_from_ref = options.mdfr
    min_samp = options.minsamp

    try:
        clear()
        dots = 0
        conn = sqlite3.connect(database_name)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS intersects (time INTEGER, latitude REAL, longitude REAL)")

        receivers = []
        with open(rx_file, "r") as file2:
            receiver_list = file2.readlines()
            for x in receiver_list:
                receivers.append(receiver(x.replace('\n', '')))

        avg_list = []
        average_intersects = np.array([]).reshape(0,2)

        while True:
            print("Receiving" + dots*'.')
            print("Press Control+C to process data and exit.")
            intersect_list = np.array([]).reshape(0,3)
            for x in range(len(receivers)):
                for y in range(x):
                    if x != y:
                        try:
                            if receivers[x].confidence > min_conf and receivers[y].confidence > min_conf:
                                intersection = list(plot_intersects(receivers[x].latitude, receivers[x].longitude,
                                receivers[x].doa, receivers[y].latitude, receivers[y].longitude, receivers[y].doa))
                                print(intersection)
                                avg_pwr = np.mean([receivers[x].power, receivers[y].power])
                                intersection.append(avg_pwr)
                                intersection = np.array([intersection])
                                # print(f"Intersect: {intersection}")
                                if intersection.any() != None:
                                    intersect_list = np.concatenate((intersect_list, intersection), axis=0)
                                    #print(intersect_list)
                        except TypeError: # I can't figure out what's causing me to need this here
                            pass

            pwr_list = []
            delete_these = []
            if intersect_list.size != 0:
                #print(intersect_list)
                if intersect_list.size > 1:
                    for x in range(len(intersect_list)):
                        pwr_list.append(intersect_list[x, 2])
                    reference_pt = pwr_list.index(max(pwr_list))
                    for x in range(len(intersect_list)):
                        if x != reference_pt:
                            # print(f"Checking point: {intersect_list[x]} against reference {intersect_list[reference_pt]}")
                            dist = v.inverse(intersect_list[reference_pt, 0:2], intersect_list[x, 0:2])[0]
                            if dist > max_dist_from_ref:
                                delete_these.append(x) #deleting elements too early causes problems!
                    if not delete_these:
                        for x in delete_these:
                            intersect_list = np.delete(intersect_list, x, 0)
                            # print("Deleted Bad Intersection")

                avg_coord = np.mean(intersect_list, axis = 0)
                to_table = [receivers[x].doa_time, avg_coord[0], avg_coord[1]]
                # print(to_table)
                c.execute("INSERT INTO intersects VALUES (?,?,?)", to_table)
                conn.commit()

            for rx in receivers:
                rx.update()
            time.sleep(1)
            if dots > 5:
                dots = 1
            else:
                dots += 1
            clear()

    except KeyboardInterrupt:
        clear()
        print("Processing, please wait.")
        conn.commit()
        conn.close()
        process_data(database_name, geofile, eps, min_samp)

        quit()

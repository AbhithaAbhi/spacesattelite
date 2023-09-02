import sgp4
from sgp4.earth_gravity import wgs72
from sgp4.io import twoline2rv
import pyproj
from datetime import datetime, timedelta
import concurrent.futures
import logging

# Initialize logger
logging.basicConfig(filename='satellite_tracking.log', level=logging.INFO)

# Step 1: Get Satellite Location
def get_satellite_positions(tle_lines, num_minutes=1440):
    positions = []
    tle_sets = [tle_lines[i:i + 3] for i in range(0, len(tle_lines), 3)]

    for tle_set in tle_sets:
        satellite = twoline2rv(tle_set[1], tle_set[2], wgs72)
        current_time = datetime.utcnow()

        for i in range(num_minutes):
            time = current_time + timedelta(minutes=i)
            try:
                position, _ = satellite.propagate(
                    time.year, time.month, time.day, time.hour,
                    time.minute, time.second + time.microsecond / 1e6
                )
                positions.append((time, position))
            except Exception as e:
                logging.error(f"Error propagating satellite position: {e}")

    return positions

# Step 2: Convert data to Lat-Long-Alt format
def transform_data(positions):
    ecef = pyproj.CRS("EPSG:4978")
    lla = pyproj.CRS("EPSG:4326")
    transformer = pyproj.Transformer.from_crs(ecef, lla, always_xy=True)

    pos_x = [pos[0] for _, pos in positions]
    pos_y = [pos[1] for _, pos in positions]
    pos_z = [pos[2] for _, pos in positions]

    lons, lats, alts = transformer.transform(pos_x, pos_y, pos_z)
    return list(zip(lats, lons, alts))

# Step 3: Find when it is going over a certain lat-long region
def is_in_bounding_box(coord, box):
    lat, lon = coord
    lat_min, lon_min, lat_max, lon_max = box
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max

# Step 4: Optimize code to reduce computation time
def process_satellite_chunk(chunk, bounding_box):
    filtered_data = []
    for (time, position) in chunk:
        lat, lon, _ = position
        if is_in_bounding_box((lat, lon), bounding_box):
            filtered_data.append(f"Time: {time}, Latitude: {lat}, Longitude: {lon}")
    return filtered_data

def compute_bounding_box(positions):
    latitudes, longitudes, _ = zip(*[pos[1] for pos in positions])
    lat_min = min(latitudes)
    lat_max = max(latitudes)
    lon_min = min(longitudes)
    lon_max = max(longitudes)
    return (lat_min, lon_min, lat_max, lon_max)

# Main function
def main():
    with open('30000sats.txt', 'r') as file:
        tle_data = file.readlines()

    # Get satellite positions
    positions = get_satellite_positions(tle_data)

    bounding_box = compute_bounding_box(positions)

    num_processes = 4
    chunk_size = len(positions) // num_processes
    chunks = [positions[i:i + chunk_size] for i in range(0, len(positions), chunk_size)]

    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = executor.map(process_satellite_chunk, chunks, [bounding_box] * len(chunks))

    filtered_data = [result for chunk_result in results for result in chunk_result]
    for result in filtered_data:
        print(result, flush=True)

if __name__ == "__main__":
    main()

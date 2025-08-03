# Generate negative samples using local CSV fire archive data

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import math

# === CONFIG ===
INPUT_FILE = "subset.xlsx"  # Your fire incident data
FIRE_ARCHIVE_CSV = "fire_archive_M-C61_641811.csv"  # Local fire archive
OUTPUT_FILE = "fire_points_check_10_rows.xlsx"  # Output with 5 points per fire

# Sampling parameters
POINTS_PER_FIRE = 5  # 5 random points per fire incident
BUFFER_RADIUS_KM = 10  # Search within 10km radius of fire location
MIN_DISTANCE_KM = 2   # Minimum 2km away from fire point
FIRE_DETECTION_BUFFER_KM = 1.0  # Consider fire detected if within 1km
DATE_RANGE_DAYS = 3   # Check ±3 days around fire date
MAX_ROWS_TO_PROCESS = 10  # Process only first 10 rows for testing

def load_fire_archive():
    """Load and prepare fire archive data"""
    print("📖 Loading fire archive data...")
    try:
        fire_archive = pd.read_csv(FIRE_ARCHIVE_CSV)
        
        # Convert date column to datetime
        fire_archive['acq_date'] = pd.to_datetime(fire_archive['acq_date'])
        
        print(f"📊 Loaded {len(fire_archive)} fire records from archive")
        print(f"📅 Date range: {fire_archive['acq_date'].min()} to {fire_archive['acq_date'].max()}")
        
        return fire_archive
    except Exception as e:
        print(f"❌ Error loading fire archive: {e}")
        return None

def generate_random_point_in_buffer(center_lat, center_lon, min_distance_km, max_distance_km):
    """Generate a random point within buffer zone but outside minimum distance"""
    while True:
        # Generate random angle and distance
        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(min_distance_km, max_distance_km)
        
        # Calculate new coordinates using proper spherical geometry
        # Convert distance to degrees (approximate)
        lat_offset = (distance / 111.0) * math.cos(angle)  # 111 km per degree latitude
        lon_offset = (distance / (111.0 * math.cos(math.radians(center_lat)))) * math.sin(angle)
        
        new_lat = center_lat + lat_offset
        new_lon = center_lon + lon_offset
        
        # Validate coordinates (bounds check for Nepal/region)
        if 26.0 <= new_lat <= 31.0 and 80.0 <= new_lon <= 89.0:
            return new_lat, new_lon

def calculate_distance_km(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in kilometers using Haversine formula"""
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r

def check_fire_in_archive(fire_archive, lat, lon, date, buffer_km=FIRE_DETECTION_BUFFER_KM, date_range_days=DATE_RANGE_DAYS):
    """Check if fire occurred near this location and date in the archive"""
    try:
        # Create date range for checking
        start_date = date - timedelta(days=date_range_days)
        end_date = date + timedelta(days=date_range_days)
        
        # Filter archive by date range
        date_filtered = fire_archive[
            (fire_archive['acq_date'] >= start_date) & 
            (fire_archive['acq_date'] <= end_date)
        ]
        
        if len(date_filtered) == 0:
            return False, 0  # No fires in date range
        
        # Check spatial proximity
        fire_found = False
        min_distance = float('inf')
        
        for _, fire_record in date_filtered.iterrows():
            distance = calculate_distance_km(lat, lon, fire_record['latitude'], fire_record['longitude'])
            min_distance = min(min_distance, distance)
            
            if distance <= buffer_km:
                fire_found = True
                break
        
        return fire_found, min_distance if min_distance != float('inf') else 999
        
    except Exception as e:
        print(f"   ⚠️  Error checking archive: {e}")
        return False, 999

def generate_points_for_fires():
    """Generate random points around fire locations and check for fire presence"""
    try:
        # Load data
        print("📖 Loading fire incident data...")
        fire_df = pd.read_excel(INPUT_FILE)
        
        # Take only first MAX_ROWS_TO_PROCESS rows for testing
        fire_df = fire_df.head(MAX_ROWS_TO_PROCESS)
        
        fire_archive = load_fire_archive()
        if fire_archive is None:
            return
        
        print(f"🔢 Processing {len(fire_df)} fire incidents")
        print(f"🎯 Generating {POINTS_PER_FIRE} random points per fire")
        print("=" * 80)
        
        results = []
        
        for index, fire_row in fire_df.iterrows():
            try:
                fire_lat = fire_row['LATITUDE']
                fire_lon = fire_row['LONGITUDE']
                fire_date = pd.to_datetime(fire_row['ACQ_DATE'])
                district = fire_row.get('DISTRICT', 'Unknown')
                
                print(f"\n🔥 Fire {index + 1}/{len(fire_df)}: {district}")
                print(f"   📍 Fire location: {fire_lat:.5f}, {fire_lon:.5f}")
                print(f"   📅 Fire date: {fire_date.date()}")
                
                # Generate result row starting with fire info
                result_row = {
                    'fire_id': index + 1,
                    'fire_latitude': fire_lat,
                    'fire_longitude': fire_lon,
                    'fire_date': fire_date,
                    'district': district
                }
                
                # Generate 5 random points
                for point_num in range(1, POINTS_PER_FIRE + 1):
                    print(f"   🎲 Generating point {point_num}...")
                    
                    # Generate random point in buffer zone
                    sample_lat, sample_lon = generate_random_point_in_buffer(
                        fire_lat, fire_lon, MIN_DISTANCE_KM, BUFFER_RADIUS_KM
                    )
                    
                    # Check if fire occurred at this location
                    has_fire, min_distance = check_fire_in_archive(
                        fire_archive, sample_lat, sample_lon, fire_date
                    )
                    
                    # Distance from original fire
                    distance_from_fire = calculate_distance_km(fire_lat, fire_lon, sample_lat, sample_lon)
                    
                    # Add to result row
                    result_row[f'point_{point_num}_lat'] = sample_lat
                    result_row[f'point_{point_num}_lon'] = sample_lon
                    result_row[f'point_{point_num}_fire'] = 'yes' if has_fire else 'no'
                    result_row[f'point_{point_num}_distance_from_fire_km'] = round(distance_from_fire, 2)
                    result_row[f'point_{point_num}_nearest_fire_km'] = round(min_distance, 2) if min_distance != 999 else 'none'
                    
                    fire_status = "🔥 FIRE" if has_fire else "❄️ NO FIRE"
                    print(f"      📍 Point {point_num}: {sample_lat:.5f}, {sample_lon:.5f}")
                    print(f"      📏 {distance_from_fire:.2f}km from original fire")
                    print(f"      🎯 Status: {fire_status}")
                    if has_fire:
                        print(f"      📍 Nearest fire: {min_distance:.2f}km away")
                
                results.append(result_row)
                
            except Exception as e:
                print(f"   ❌ Error processing fire {index + 1}: {e}")
                continue
        
        # Create DataFrame and save
        results_df = pd.DataFrame(results)
        results_df.to_excel(OUTPUT_FILE, index=False)
        
        # Summary statistics
        total_points = len(results) * POINTS_PER_FIRE
        fire_points = 0
        no_fire_points = 0
        
        for point_num in range(1, POINTS_PER_FIRE + 1):
            fire_count = len(results_df[results_df[f'point_{point_num}_fire'] == 'yes'])
            fire_points += fire_count
        
        no_fire_points = total_points - fire_points
        
        print("\n" + "=" * 80)
        print("🎉 Point generation complete!")
        print(f"📊 Summary statistics:")
        print(f"   🔥 Total fires processed: {len(results)}")
        print(f"   📍 Total points generated: {total_points}")
        print(f"   🔥 Points with fire detected: {fire_points}")
        print(f"   ❄️  Points with NO fire: {no_fire_points}")
        print(f"   📈 No-fire percentage: {(no_fire_points/total_points)*100:.1f}%")
        print(f"📁 Output file: {OUTPUT_FILE}")
        
        # Show column structure
        print(f"\n📋 Output columns:")
        for i, col in enumerate(results_df.columns, 1):
            print(f"   {i:2d}. {col}")
        
        # Show sample data
        print(f"\n📄 Sample of first 2 fires:")
        sample_cols = ['fire_id', 'district', 'point_1_fire', 'point_2_fire', 'point_3_fire', 'point_4_fire', 'point_5_fire']
        print(results_df[sample_cols].head(2))
        
        return results_df
        
    except Exception as e:
        print(f"❌ Error in point generation: {e}")
        import traceback
        traceback.print_exc()

# === MAIN EXECUTION ===
if __name__ == "__main__":
    print("🎯 Fire Point Generation and Validation")
    print("📊 Using Local CSV Fire Archive for Validation")
    print("🧪 Processing First 10 Fires for Testing")
    print("=" * 60)
    
    generate_points_for_fires()
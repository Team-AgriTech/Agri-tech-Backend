# Weather enrichment script for clean fire data - SAFE VERSION

import pandas as pd
import requests
from datetime import datetime
import time
import os

# === SAFER CONFIG ===
NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETERS = "T2M,RH2M,WS2M,PRECTOTCORR"
COMMUNITY = "RE"
FORMAT = "JSON"
INPUT_FILE = "subset.xlsx"
OUTPUT_FILE = "enriched_fire_data_1000_rows.xlsx"  # Updated filename
CHECKPOINT_FILE = "processing_checkpoint.xlsx"
MAX_ROWS = 1000  # Process all 1000 rows at once
FIRE_LABEL = 1
CHECKPOINT_INTERVAL = 25  # Save progress every 25 rows
DELAY_BETWEEN_REQUESTS = 2  # 2 seconds (safe)
MAX_RETRIES = 3  # Retry failed requests

# === FUNCTION TO SAVE PROGRESS ===
def save_checkpoint(df, processed_count):
    """Save current progress to checkpoint file"""
    df.to_excel(CHECKPOINT_FILE, index=False)
    print(f"💾 Checkpoint saved! Progress: {processed_count} rows completed")

# === FUNCTION TO LOAD PREVIOUS PROGRESS ===
def load_checkpoint():
    """Load previous progress if exists"""
    if os.path.exists(CHECKPOINT_FILE):
        print(f"📁 Found checkpoint file. Loading previous progress...")
        return pd.read_excel(CHECKPOINT_FILE)
    return None

# === FUNCTION TO FORMAT DATE ===
def format_date(date_obj):
    """Convert datetime object to YYYYMMDD format for NASA API"""
    try:
        if isinstance(date_obj, str):
            dt = datetime.strptime(date_obj, "%Y-%m-%d %H:%M:%S")
        else:
            dt = date_obj
        
        return dt.strftime("%Y%m%d")
    except Exception as e:
        print(f"Error parsing date {date_obj}: {e}")
        return None

# === IMPROVED WEATHER DATA FUNCTION WITH RETRY ===
def get_weather_data_with_retry(lat, lon, date, max_retries=MAX_RETRIES):
    """Fetch weather data with retry logic and exponential backoff"""
    for attempt in range(max_retries):
        try:
            params = {
                "parameters": PARAMETERS,
                "start": date,
                "end": date,
                "latitude": lat,
                "longitude": lon,
                "format": FORMAT,
                "community": COMMUNITY
            }
            
            print(f"   🌤️  Fetching weather (attempt {attempt + 1}/{max_retries})")
            response = requests.get(NASA_POWER_URL, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            props = data["properties"]["parameter"]
            
            weather_data = {
                "T2M": props["T2M"].get(date, None),
                "RH2M": props["RH2M"].get(date, None),
                "WS2M": props["WS2M"].get(date, None),
                "PRECTOTCORR": props["PRECTOTCORR"].get(date, None)
            }
            
            print(f"   ✅ Success! T2M={weather_data['T2M']}°C, RH2M={weather_data['RH2M']}%, WS2M={weather_data['WS2M']}m/s, PREC={weather_data['PRECTOTCORR']}mm")
            return weather_data
            
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Attempt {attempt + 1} failed: HTTP Error - {e}")
        except KeyError as e:
            print(f"   ❌ Attempt {attempt + 1} failed: Data parsing error - {e}")
        except Exception as e:
            print(f"   ❌ Attempt {attempt + 1} failed: {e}")
        
        # If not the last attempt, wait with exponential backoff
        if attempt < max_retries - 1:
            wait_time = (attempt + 1) * 2  # 2s, 4s, 6s...
            print(f"   ⏳ Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)
    
    print(f"   💥 All {max_retries} attempts failed - using NULL values")
    return {"T2M": None, "RH2M": None, "WS2M": None, "PRECTOTCORR": None}

# === MAIN FUNCTION TO ENRICH FIRE DATA ===
def enrich_fire_data():
    """Process clean fire data Excel and enrich with weather data - SAFE VERSION"""
    try:
        # Check if we can resume from checkpoint
        checkpoint_df = load_checkpoint()
        if checkpoint_df is not None:
            resume = input("Found previous progress. Resume from checkpoint? (y/n): ").lower() == 'y'
            if resume:
                print("📈 Resuming from checkpoint...")
                df_subset = checkpoint_df
                # Find where to resume (look for rows without weather data)
                mask = df_subset["T2M"].isna()
                start_index = df_subset[mask].index[0] if mask.any() else len(df_subset)
                processed_count = start_index
            else:
                print("🆕 Starting fresh...")
                os.remove(CHECKPOINT_FILE)
                start_index = 0
                processed_count = 0
                df_subset = None
        else:
            start_index = 0
            processed_count = 0
            df_subset = None
        
        # If not resuming, load original data
        if df_subset is None:
            print(f"📖 Reading Excel file: {INPUT_FILE}")
            df = pd.read_excel(INPUT_FILE)
            
            print(f"📊 Total rows in file: {len(df)}")
            print(f"🔢 Processing first {MAX_ROWS} rows")
            print(f"📋 Columns: {list(df.columns)}")
            print("=" * 80)
            
            # Take only first MAX_ROWS
            df_subset = df.head(MAX_ROWS).copy()
            
            # Initialize new columns for weather data
            df_subset["T2M"] = None
            df_subset["RH2M"] = None
            df_subset["WS2M"] = None
            df_subset["PRECTOTCORR"] = None
            
            # 🔥 ADD FIRE LABEL COLUMN
            df_subset["fire"] = FIRE_LABEL
            print(f"🏷️  Added 'fire' column with value: {FIRE_LABEL}")
        
        failed_count = 0
        start_time = datetime.now()
        
        print(f"🚀 Starting processing from row {start_index + 1}...")
        
        for index, row in df_subset.iterrows():
            # Skip rows that are already processed
            if index < start_index:
                continue
                
            try:
                # Extract data from your clean format
                lat = float(row["LATITUDE"])
                lon = float(row["LONGITUDE"])
                acq_date = row["ACQ_DATE"]
                
                print(f"\n🔥 Row {index + 1}/{MAX_ROWS}: Processing fire incident")
                print(f"   📍 Location: {lat:.5f}, {lon:.5f}")
                print(f"   📅 Date: {acq_date}")
                print(f"   🏛️  District: {row.get('DISTRICT', 'N/A')}")
                print(f"   🏷️  Fire Label: {FIRE_LABEL}")
                
                # Format date for NASA API
                formatted_date = format_date(acq_date)
                if not formatted_date:
                    print(f"   ⚠️  Skipping row due to invalid date format")
                    failed_count += 1
                    continue
                
                # Get weather data with retry logic
                weather = get_weather_data_with_retry(lat, lon, formatted_date)
                
                # Update DataFrame with weather data
                df_subset.at[index, "T2M"] = weather["T2M"]
                df_subset.at[index, "RH2M"] = weather["RH2M"]
                df_subset.at[index, "WS2M"] = weather["WS2M"]
                df_subset.at[index, "PRECTOTCORR"] = weather["PRECTOTCORR"]
                
                processed_count += 1
                
                # Calculate ETA
                elapsed = datetime.now() - start_time
                if processed_count > 0:
                    avg_time_per_row = elapsed.total_seconds() / (processed_count - start_index)
                    remaining_rows = MAX_ROWS - processed_count
                    eta_seconds = remaining_rows * avg_time_per_row
                    eta_minutes = eta_seconds / 60
                    print(f"   ⏱️  ETA: ~{eta_minutes:.1f} minutes remaining")
                
                print(f"   ✅ Row {index + 1} processed successfully ({processed_count}/{MAX_ROWS})")
                
                # Save checkpoint periodically
                if processed_count % CHECKPOINT_INTERVAL == 0:
                    save_checkpoint(df_subset, processed_count)
                
                # Increased delay for safety
                print(f"   ⏳ Waiting {DELAY_BETWEEN_REQUESTS} seconds...")
                time.sleep(DELAY_BETWEEN_REQUESTS)
                
            except ValueError as e:
                print(f"   ⚠️  Row {index + 1}: Invalid latitude/longitude values - {e}")
                failed_count += 1
                continue
            except KeyError as e:
                print(f"   ⚠️  Row {index + 1}: Missing required column - {e}")
                failed_count += 1
                continue
            except Exception as e:
                print(f"   ❌ Row {index + 1}: Unexpected error - {e}")
                failed_count += 1
                continue
        
        # Save final result
        df_subset.to_excel(OUTPUT_FILE, index=False)
        
        # Clean up checkpoint file
        if os.path.exists(CHECKPOINT_FILE):
            os.remove(CHECKPOINT_FILE)
        
        # Final summary
        total_time = datetime.now() - start_time
        print("=" * 80)
        print(f"🎉 Processing complete!")
        print(f"⏱️  Total time: {total_time}")
        print(f"📊 Total rows processed successfully: {processed_count}")
        print(f"❌ Total rows failed: {failed_count}")
        print(f"📁 Output file: {OUTPUT_FILE}")
        
        # Show sample of enriched data
        print(f"\n📄 Sample of enriched data:")
        sample_cols = ['DISTRICT', 'LATITUDE', 'LONGITUDE', 'T2M', 'RH2M', 'WS2M', 'PRECTOTCORR', 'fire']
        print(df_subset[sample_cols].head(3))
        
    except FileNotFoundError:
        print(f"❌ Error: Input file '{INPUT_FILE}' not found!")
    except KeyboardInterrupt:
        print(f"\n⏹️  Process interrupted by user")
        print(f"💾 Progress has been saved to checkpoint file")
        print(f"🔄 Run the script again to resume from where you left off")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

# === MAIN EXECUTION ===
if __name__ == "__main__":
    print("🔥 Fire Data Weather Enrichment Script - SAFE VERSION")
    print("🌤️  Adding NASA POWER Weather Data (T2M, RH2M, WS2M, PRECTOTCORR)")
    print("🏷️  Adding Fire Label Column for Model Training")
    print("🛡️  Features: Retry logic, Checkpoints, ETA calculation")
    print("=" * 70)
    enrich_fire_data()
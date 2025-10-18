# Import necessary libraries
from itertools import groupby
import pandas as pd
import numpy as np
import openpyxl
import duckdb
import warnings
import matplotlib.pyplot as plt
import seaborn as sns
import gspread
from google.auth import default
from google.colab import auth
from google.colab import drive
import polars as pl
from tqdm.notebook import tqdm  # Progress bar for pandas operations

# todo - add rev share per max level reached. need revenue data
# todo - add end of day status by percentile
# todo - add data by iteration
# todo - add wager data to calculate payout
# todo - distribution for purchases
# todo - add dice factor in specific days

# Mount Google Drive
print("Mounting Google Drive...")
drive.mount('/content/gdrive')
print("Google Drive mounted successfully.")

# Suppress warnings because who cares
warnings.filterwarnings('ignore')

# Establish DuckDB connection
print("Establishing DuckDB connection...")
conn = duckdb.connect()
print("DuckDB connection established.")

# Authenticate Google account for accessing Google Sheets
print("Authenticating Google account...")
auth.authenticate_user()
creds, _ = default()
gc = gspread.authorize(creds)
print("Google account authenticated successfully.")

# Access the Google Sheets spreadsheet
print("Accessing Google Sheets spreadsheet...")

# Insert spreadsheet key below:
spreadsheet = gc.open_by_key('')
print("Spreadsheet accessed successfully.")

# Define the data path and date range for filtering
data_path = '/content/gdrive/MyDrive/TileHunt_Sim/'
start_date = pd.to_datetime('2025-04-21 10:00:00')
end_date = pd.to_datetime('2025-04-28 09:59:00')

# Load and preprocess tile hunt data
print("Loading tile hunt data...")
tile_hunt_data = pd.read_csv(data_path + 'tile_hunt_data.csv')
tile_hunt_data.columns = tile_hunt_data.columns.str.lower()
tile_hunt_data['eventtime'] = pd.to_datetime(tile_hunt_data['eventtime'])
tile_hunt_data['date'] = tile_hunt_data['eventtime'].dt.date
tile_hunt_data['event_day_start'] = (tile_hunt_data['eventtime'] - pd.Timedelta(hours=10)).dt.date
tile_hunt_data = tile_hunt_data.rename(columns={'bar_id': 'milestone_id'})
tile_hunt_data_filtered = tile_hunt_data[(tile_hunt_data['eventtime'] >= start_date) & (tile_hunt_data['eventtime'] <= end_date)]

tile_hunt_data_qa = tile_hunt_data[tile_hunt_data['config_id']=='DiceMG_Event_March24_1742222388881']
print(f"Tile hunt data loaded and filtered. Number of records: {len(tile_hunt_data_filtered)}")

# Load configuration data from Google Sheets
print("Loading configuration data from Google Sheets...")
try:
    mg_distribution_sheet = spreadsheet.worksheet("MGs Distribution")
    mg_distribution = pd.DataFrame(mg_distribution_sheet.get())

    main_config_sheet = spreadsheet.worksheet("TileHunt Config")
    main_config = pd.DataFrame(main_config_sheet.get())
    print("Configuration data loaded successfully.")
except gspread.exceptions.WorksheetNotFound:
    print("Error: One or both worksheet names are incorrect. Please check the names in Google Sheets.")

# Preprocess MG distribution data
print("Preprocessing MG distribution data...")
mg_distribution.columns = mg_distribution.iloc[0]
mg_distribution = mg_distribution.drop(0)
mg_distribution.columns = mg_distribution.columns.str.lower()
mg_distribution = mg_distribution[['feature', 'config_id', 'milestone_id', 'mgs', 'config_name']]
mg_distribution['mgs'] = mg_distribution['mgs'].astype(int)
mg_distribution['milestone_id'] = mg_distribution['milestone_id'].astype(int)
print("MG distribution data preprocessed.")

# Preprocess main configuration data
print("Preprocessing main configuration data...")
main_config.columns = main_config.iloc[0]
main_config = main_config.drop(0)
main_config.columns = main_config.columns.str.lower()
main_config = main_config[['level', 'picks_from', 'picks_to', 'energy']]
main_config['picks_from'] = main_config['picks_from'].astype(float)
main_config['picks_to'] = main_config['picks_to'].astype(float)
main_config['energy'] = main_config['energy'].astype(float)
main_config['cumu_energy'] = main_config.groupby('level')['energy'].cumsum()
print("Main configuration data preprocessed.")

# Merge tile hunt data with MG distribution
print("Merging tile hunt data with MG distribution...")
player_collection = tile_hunt_data_filtered.merge(mg_distribution, on=['config_id', 'milestone_id'], how='left')
player_collection.sort_values(by=['playerid', 'date'], inplace=True)
player_collection = player_collection.dropna(subset=['mgs']) # todo - check if we need to remove this dropna to include players that didn't collect anything
print(f"Data merged. Number of player records: {len(player_collection)}")

# Aggregate MGS collected per player per day
print("Aggregating MGS collected per player per day...")
score_data = player_collection.groupby(['playerid', 'event_day_start'])['mgs'].sum().reset_index()
score_data.sort_values(by=['playerid', 'event_day_start'], inplace=True)
score_data.rename(columns={'mgs': 'mgs_collected'}, inplace=True)
score_data['cumu_mgs_collected'] = score_data.groupby('playerid')['mgs_collected'].cumsum()
print("Aggregation complete.")

# Join with main configuration to determine levels
print("Joining with main configuration to determine levels...")
score_data = conn.execute(f'''
SELECT *
FROM score_data AS s
LEFT JOIN main_config AS m
ON s.cumu_mgs_collected >= m.picks_from
AND s.cumu_mgs_collected < m.picks_to
''').df()
score_data['event_day_start'] = pd.to_datetime(score_data['event_day_start']).dt.date
print("Join complete.")

# Create unique dates DataFrame and assign event days
print("Creating unique dates DataFrame and assigning event days...")
unique_dates = tile_hunt_data_filtered['event_day_start'].unique()
unique_dates_df = pd.DataFrame({'event_day_start': unique_dates})
unique_dates_df.sort_values(by='event_day_start', inplace=True)
unique_dates_df['event_day'] = range(1, len(unique_dates_df) + 1)
print("Unique dates DataFrame created.")

# Merge score data with unique dates to get event days
print("Merging score data with unique dates to get event days...")
score_data = pd.merge(score_data, unique_dates_df, on='event_day_start', how='inner')
score_data.sort_values(by=['playerid', 'event_day_start'], inplace=True)
score_data.fillna(0, inplace=True)
score_data['level'] = score_data['level'].astype(int)
print("Merge complete.")

# Filter score data for valid levels and event days
print("Filtering score data for valid levels and event days...")
score_data_filtered = score_data[score_data['level'] != 0]
score_data_filtered = score_data_filtered[score_data_filtered['event_day'] < 8]
print(f"Filtered score data. Number of records: {len(score_data_filtered)}")

# Aggregate maximum level achieved per player
print("Aggregating maximum level achieved per player...")
data_agg = score_data_filtered.groupby(['playerid'])['level'].max().reset_index()

print('Analysis completed successfully')

print('Visulizing data...')

# Group data for plotting
mg_distribution_by_feature = player_collection.groupby(['event_day_start', 'feature'])['mgs'].sum().reset_index()

# Pivot the data to create a matrix suitable for stacked bar chart
pivot_table = mg_distribution_by_feature.pivot(index='event_day_start', columns='feature', values='mgs')

# Calculate percentages for each Feature within each EventTime
pivot_table_percentage = pivot_table.div(pivot_table.sum(axis=1), axis=0) * 100

# Create the stacked bar chart
ax = pivot_table_percentage.plot(kind='bar', stacked=True, figsize=(12, 6))

# Annotate bars with percentages
for container in ax.containers:
  for i, rect in enumerate(container):
    height = rect.get_height()
    if height > 0:  # Prevent annotation on bars with zero height
      ax.text(rect.get_x() + rect.get_width() / 2, rect.get_y() + height / 2, f'{height:.1f}%', ha='center', va='center', fontsize=8, color='white' if height < 50 else 'black') # Adjust color for visibility


plt.title('MGs Distribution by Feature per Event Day (100% Stacked)')
plt.xlabel('event_day_start')
plt.ylabel('Percentage of MGs')
plt.xticks(rotation=45, ha='right')  # Rotate x-axis labels for readability
plt.tight_layout()
plt.show()
print('\n')

# Get each player's final level completed (max level across event days)
final_levels = score_data_filtered.groupby('playerid')['level'].max().reset_index()

# Count how many players ended up at each level
level_counts = final_levels['level'].value_counts().sort_index().reset_index()
level_counts.columns = ['level_completed', 'unique_players']
total_players = level_counts['unique_players'].sum()
level_counts['percentage'] = (level_counts['unique_players'] / total_players) * 100


# Plot the histogram
plt.figure(figsize=(12, 6))
bars = plt.bar(level_counts['level_completed'], level_counts['unique_players'], color='steelblue')

# Add data labels
for bar in bars:
    height = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2, height + 5, f'{int(height)}', ha='center', va='bottom')

# Formatting
plt.title('Number of Unique Players by Levels Completed (End of Event)', fontsize=14)
plt.xlabel('Final Level Completed', fontsize=12)
plt.ylabel('Number of Players', fontsize=12)
plt.xticks(level_counts['level_completed'])
plt.grid(axis='y', linestyle='--', alpha=0.4)
plt.tight_layout()

plt.show()
print('\n')

# Plot percentage of players per level
plt.figure(figsize=(12, 6))
bars = plt.bar(level_counts['level_completed'], level_counts['percentage'], color='skyblue', edgecolor='black')

# Annotate each bar with percentage value
for bar in bars:
    height = bar.get_height()
    if height > 0:
        plt.text(bar.get_x() + bar.get_width()/2, height + 0.3, f'{height:.1f}%',
                 ha='center', va='bottom', fontsize=10, color='black')

# Formatting
plt.title('Percentage of Unique Players by Levels Completed (End of Event)', fontsize=14)
plt.xlabel('Final Level Completed', fontsize=12)
plt.ylabel('Percentage of Players (%)', fontsize=12)
plt.xticks(level_counts['level_completed'])
plt.ylim(0, max(level_counts['percentage']) * 1.2)  # Add headroom
plt.grid(axis='y', linestyle='--', alpha=0.5)
plt.tight_layout()

plt.show()
print('\n')

# Copy and increment the level to reflect where players got stuck
dropoff_data = score_data_filtered.copy()
dropoff_data['stuck_level'] = dropoff_data['level'] + 1

# Group by event day and new "stuck level"
dropoff_counts = dropoff_data.groupby(['stuck_level', 'event_day'])['playerid'].nunique().reset_index()
dropoff_counts.rename(columns={'playerid': 'unique_players'}, inplace=True)

# Pivot the data for heatmap format
heatmap_data = dropoff_counts.pivot(index='stuck_level', columns='event_day', values='unique_players')
heatmap_data = heatmap_data.fillna(0)  # Fill missing combinations with zero

# Set the plot style
plt.figure(figsize=(14, 8))
sns.set(font_scale=1.0)

# Plot the heatmap with annotations
ax = sns.heatmap(
    heatmap_data,
    cmap='YlGnBu',              # Color scheme
    annot=True,                 # Show numbers
    fmt='.0f',                  # No decimals
    linewidths=0.5,             # Light grid lines
    linecolor='gray',
    cbar_kws={'label': 'Unique Players'}
)

# Customize the plot
plt.title('Unique Players per Level per Event Day', fontsize=16)
plt.xlabel('Event Day', fontsize=12)
plt.ylabel('Level', fontsize=12)
plt.tight_layout()

plt.show()
print('\n')

# Calculate percentiles
percentiles = [50, 75, 90, 95, 99]
percentile_values = data_agg['level'].quantile(q=np.array(percentiles)/100)
mean_level = data_agg['level'].mean()

# Create a dictionary to store the data for the bar chart
data = {
    'Percentile': ['50th', 'Mean', '75th', '90th', '95th', '99th'],
    'Max Level': [percentile_values[0.5], mean_level, percentile_values[0.75], percentile_values[0.9], percentile_values[0.95], percentile_values[0.99]]
}

# Create a DataFrame
percentile_df = pd.DataFrame(data)

# Create the bar chart
plt.figure(figsize=(12, 6))
bars = plt.bar(percentile_df['Percentile'], percentile_df['Max Level'], color='skyblue')

# Add value labels on top of each bar
for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2, yval + 0.5, f"{yval:.1f}",
             ha='center', va='bottom', fontsize=10)

plt.xlabel("Percentile")
plt.ylabel("Max Level")
plt.title("Levels Completed by Percentile")
plt.tight_layout()
plt.show()

print('\n')

# Group by 'date' and sum 'mgs_collected'
daily_mg_sum = score_data.groupby('event_day')['mgs_collected'].sum().reset_index()

# Create the bar chart
plt.figure(figsize=(12, 6))
bars = plt.bar(daily_mg_sum['event_day'], daily_mg_sum['mgs_collected'])

# Add the value on top of each bar
for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2, yval, round(yval), ha='center', va='bottom')

plt.xlabel('Day')
plt.ylabel('Sum of MGs Collected')
plt.title('Sum of MGs Collected per Day')
plt.tight_layout()  # Adjust layout to prevent labels from overlapping
plt.show()
print('\n')

# Group by 'date' and calculate the average 'mgs_collected'
daily_avg_mg = score_data.groupby('event_day')['mgs_collected'].mean().reset_index()

# Create the bar chart
plt.figure(figsize=(12, 6))
bars = plt.bar(daily_avg_mg['event_day'], daily_avg_mg['mgs_collected'])

# Add the value on top of each bar
for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2, yval, round(yval), ha='center', va='bottom')

plt.xlabel('Day')
plt.ylabel('Average MGs Collected')
plt.title('Average MGs Collected per Day')
plt.tight_layout()  # Adjust layout to prevent labels from overlapping
plt.show()
print('\n')

# Calculate average cumulative MGS collected per event day
avg_cumu_mgs_by_day = score_data_filtered.groupby('event_day')['cumu_mgs_collected'].mean().reset_index()

# Plot the average cumulative MGS collected by event day as a bar chart
plt.figure(figsize=(12, 6))
bars = plt.bar(avg_cumu_mgs_by_day['event_day'], avg_cumu_mgs_by_day['cumu_mgs_collected'], color='pink')

# Add annotations on top of each bar
for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width() / 2, yval + 5, round(yval),
             ha='center', va='bottom', fontsize=9)

plt.title('Average Cumulative MGs Collected by Event Day')
plt.xlabel('Event Day')
plt.ylabel('Avg Cumulative MGs Collected')
plt.xticks(avg_cumu_mgs_by_day['event_day'])
plt.grid(axis='y', linestyle='-', alpha=0.25)
plt.tight_layout()
plt.show()
print('\n')

# Aggregate total MGs collected per player over the event
total_mgs_per_player = score_data_filtered.groupby('playerid')['mgs_collected'].sum().reset_index()
total_mgs_per_player.rename(columns={'mgs_collected': 'total_mgs_collected'}, inplace=True)

# Calculate statistics - Median, Mean, 75th, 90th, 99th percentiles
percentiles = [50, 75, 90, 95, 99]
percentile_values = np.percentile(total_mgs_per_player['total_mgs_collected'], percentiles)
mean_value = total_mgs_per_player['total_mgs_collected'].mean()

# Prepare data for visualization
summary_stats = {
    'Metric': ['Median (50th)', 'Mean', '75th Percentile', '90th Percentile', '95th percentile', '99th Percentile'],
    'MGs Collected': [percentile_values[0], mean_value, percentile_values[1], percentile_values[2], percentile_values[3], percentile_values[4]]
}

summary_df = pd.DataFrame(summary_stats)

# Plot the bar chart
plt.figure(figsize=(12, 6))
bars = plt.bar(summary_df['Metric'], summary_df['MGs Collected'], color='darkgreen')

# Annotate bars with values
for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width() / 2, yval + (0.02 * yval), f"{round(yval, 1)}",
             ha='center', va='bottom', fontsize=10)

plt.xlabel('Percentile')
plt.ylabel('MGs Collected')
plt.title('MGs Collected per Player by Percentile (Entire Event)')
plt.tight_layout()
plt.show()



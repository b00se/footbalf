import nfl_data_py as nfl
import pandas as pd

def import_and_preprocess_weekly_data(seasons):
    weekly_data = nfl.import_weekly_data(seasons, downcast=True)
    weekly_data = weekly_data.loc[weekly_data['season_type'] == 'REG']

    weekly_data = standardize_team_names(weekly_data)

    #drop irrelevant positions
    relevent_positions = ['QB', 'RB', 'WR', 'TE']
    weekly_data = weekly_data.loc[weekly_data['position'].isin(relevent_positions)]

    #drop final week of season (week 17 before 2021)
    weekly_data = weekly_data[~((weekly_data['season'] < 2021) & (weekly_data['week'] == 17))]
    weekly_data = weekly_data[~((weekly_data['season'] >= 2021) & (weekly_data['week'] == 18))]
    return weekly_data

def import_and_preprocess_schedule_data(seasons):
    schedule = nfl.import_schedules(seasons)
    schedule = schedule.loc[nfl.import_schedules(seasons)['game_type'] == 'REG']

    return standardize_team_names(schedule, ['home_team', 'away_team'])


def standardize_team_names(df, columns=['recent_team', 'opponent_team']):
    df[columns] = df[columns].replace({'LA': 'LAR', 'OAK': 'LV'})
    return df
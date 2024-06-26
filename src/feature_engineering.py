import pandas as pd

def calculate_fantasy_points(df):
    df['dk_fp'] = df.apply(
    lambda row: round(
        row['passing_yards'] * 0.04 +
        row['passing_tds'] * 4 +
        row['interceptions'] * -1 +
        row['rushing_yards'] * 0.1 +
        row['rushing_tds'] * 6 +
        row['receiving_yards'] * 0.1 +
        row['receiving_tds'] * 6 +
        row['receptions'] * 1 +
        (row['receiving_fumbles_lost'] + row['rushing_fumbles_lost'] + row['sack_fumbles_lost'] ) * -1 +
        (row['passing_2pt_conversions'] + row['rushing_2pt_conversions'] + row['receiving_2pt_conversions']) * 2 +
        (3 if row['passing_yards'] >= 300 else 0) +
        (3 if row['rushing_yards'] >= 100 else 0) +
        (3 if row['receiving_yards'] >= 100 else 0),
        2
    ),
    axis=1)
    return df

def calculate_fp_averages(df):
    df['dk_fp_avg'] = df.groupby('player_id')['dk_fp'].transform('mean')

    # rolling averages
    df['dk_fp_last1'] = df.groupby('player_id')['dk_fp'].shift(1)
    df['dk_fp_last3'] = df.groupby('player_id')['dk_fp'].shift(1).rolling(3).mean()
    df['dk_fp_last5'] = df.groupby('player_id')['dk_fp'].shift(1).rolling(5).mean()

    # fill missing dk_fp_last3 and dk_fp_last5 with dk_fp_last1 or dk_fp_avg if available
    df['dk_fp_last3']  = df['dk_fp_last3'].fillna(df['dk_fp_last1']).fillna(df['dk_fp_avg'])
    df['dk_fp_last5']  = df['dk_fp_last5'].fillna(df['dk_fp_last3']).fillna(df['dk_fp_last1']).fillna(df['dk_fp_avg'])

    # identify players with insufficient data for rolling averages
    df['isRookie'] = df['dk_fp_last1'].isna()

    # calculate position specific averages
    position_avg_dk_fp = df.groupby('position')['dk_fp'].mean()

    # fill missing values for players with no historical data
    df['dk_fp_last1'] = df.apply(
        lambda row: position_avg_dk_fp[row['position']] if pd.isna(row['dk_fp_last1']) else row['dk_fp_last1'],
        axis=1
    )

    return df

def calculate_def_vs_pos(df):
    # calculate dkfp allowed by each defense to each position per week
    dvp = df.groupby(['season', 'week', 'opponent_team', 'position'])['dk_fp'].sum().reset_index()
    dvp.rename(columns={'opponent_team': 'defense', 'dk_fp': 'dk_fp_allowed'}, inplace=True)

    # calculate rolling cumulative average of dk_fp_allowed
    dvp['dk_fp_allowed_avg'] = dvp.groupby(['defense', 'position'])['dk_fp_allowed'].expanding().mean().reset_index(level=[0, 1], drop=True)

    # merge dvp back into main df
    df = df.merge(
        dvp[['season', 'week', 'defense', 'position', 'dk_fp_allowed_avg']],
        left_on=['season', 'week', 'opponent_team', 'position'],
        right_on=['season', 'week', 'defense', 'position'],
        how='left'
    ).drop(columns=['defense']).rename(columns={'dk_fp_allowed_avg':  'defense_vs_pos'})

    return df

def determine_is_home(weekly_df, schedule_df):
    weekly_df = weekly_df.merge(
        schedule_df[['season', 'week', 'home_team', 'away_team']],
        left_on=['season', 'week', 'recent_team'],
        right_on=['season', 'week', 'home_team'],
        how='left'
    )
    weekly_df['home'] = weekly_df['recent_team'] == weekly_df['home_team']
    weekly_df.drop(columns=['home_team', 'away_team'], inplace=True)

    return weekly_df

def calculate_implied_team_totals(schedule_df):
    betting_lines = schedule_df.loc[:, ['season', 'week', 'home_team', 'away_team', 'total_line', 'spread_line']]
    betting_lines['implied_home_total'] = betting_lines['total_line'] / 2 + betting_lines['spread_line'] / 2
    betting_lines['implied_away_total'] = betting_lines['total_line'] / 2 - betting_lines['spread_line'] / 2
    return betting_lines

def calculate_weekly_offensive_points(schedule_df):
    home_scores = schedule_df[['season', 'week', 'home_team', 'home_score']].rename(columns={'home_team': 'team', 'home_score': 'score'})
    away_scores = schedule_df[['season', 'week', 'away_team', 'away_score']].rename(columns={'away_team': 'team', 'away_score': 'score'})
    total_scores_by_week = pd.concat([home_scores, away_scores], axis=0).groupby(['season', 'week', 'team']).sum().reset_index()
    return total_scores_by_week

def calculate_weekly_offensive_points_and_averages(schedule_df):
    total_scores_by_week = calculate_weekly_offensive_points(schedule_df)
    total_scores_by_week['avg_score'] = total_scores_by_week.groupby('team')['score'].expanding().mean().round(2).reset_index(level=0, drop=True)
    # get previous week's avg. If no previous week, use avg. of all previous weeks
    total_scores_by_week['last1_avg_score'] = total_scores_by_week.groupby('team')['avg_score'].shift(1).fillna(total_scores_by_week['avg_score'].mean().round(2))
    # calculate rolling 3 week average
    total_scores_by_week['last3_avg_score'] = total_scores_by_week.groupby('team')['score'].expanding(3).mean().round(2).reset_index(level=0, drop=True).fillna(total_scores_by_week['last1_avg_score'])
    
    return total_scores_by_week

def calculate_vegas_data(schedule_df):
    betting_lines = calculate_implied_team_totals(schedule_df)
    total_scores_by_week = calculate_weekly_offensive_points_and_averages(schedule_df)

    vegas_data = pd.merge(
        betting_lines,
        total_scores_by_week[['season', 'week', 'team', 'last3_avg_score']],
        left_on=['season', 'week', 'home_team'],
        right_on=['season', 'week', 'team'],
        how='left'
    ).rename(columns={'last3_avg_score': 'home_avg_score'}).drop(columns=['team'])

    vegas_data = vegas_data.merge(
        total_scores_by_week[['season', 'week', 'team', 'last3_avg_score']],
        left_on=['season', 'week', 'away_team'],
        right_on=['season', 'week', 'team'],
        how='left'
    ).rename(columns={'last3_avg_score': 'away_avg_score'}).drop(columns=['team'])

    vegas_data['home_implied_total_diff'] = vegas_data['implied_home_total'] - vegas_data['home_avg_score']
    vegas_data['away_implied_total_diff'] = vegas_data['implied_away_total'] - vegas_data['away_avg_score']

    return vegas_data
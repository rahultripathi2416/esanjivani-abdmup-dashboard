import pandas as pd
import numpy as np

class DataEngine:
    def __init__(self, up_csv_path: str, dist_csv_path: str):
        self.up_csv_path = up_csv_path
        self.dist_csv_path = dist_csv_path
        self.df_up = None
        self.df_dist = None
        self.load_and_clean()

    @staticmethod
    def parse_flexible_date(val):
        if pd.isna(val):
            return pd.NaT
        val_str = str(val).strip().replace('-', '.')
        try:
            return pd.to_datetime(val_str, format='%d.%m.%Y')
        except Exception:
            return pd.to_datetime(val_str, errors='coerce')

    def load_and_clean(self):
        raw_up = pd.read_csv(self.up_csv_path)
        clean_up = raw_up.dropna(subset=['Date']).copy()
        clean_up['parsed_date'] = clean_up['Date'].apply(self.parse_flexible_date)
        clean_up = clean_up.dropna(subset=['parsed_date'])
        
        clean_up['teleconsultations'] = clean_up['Total Teleconsultations (Esanjeevani Report)'].fillna(0).astype(int)
        clean_up['abha_esanjivani'] = clean_up['Total                                  ABHA Created (Esanjeevani Report)'].fillna(0).astype(int)
        clean_up['abha_abdm'] = clean_up['Total ABHA created       (ABDM Insights)'].fillna(0).astype(int)
        clean_up['abha_tc'] = clean_up['Total Abha Based      Teleconsultation (Esanjeevani Report)'].fillna(0).astype(int)
        clean_up['ehr_generated'] = clean_up['Total EHR Generated (ABDM Insights)'].fillna(0).astype(int)
        clean_up['cum_abha'] = clean_up['Cummulative Abha  Created (ABDM Insights)'].fillna(0).astype(int)
        clean_up['cum_ehr'] = clean_up['Cummulative  EHR Generated (ABDM Insights)'].fillna(0).astype(int)
        self.df_up = clean_up.sort_values('parsed_date').reset_index(drop=True)

        raw_dist = pd.read_csv(self.dist_csv_path)
        clean_dist = raw_dist.dropna(subset=['Date', 'District Name']).copy()
        clean_dist['parsed_date'] = clean_dist['Date'].apply(self.parse_flexible_date)
        clean_dist = clean_dist.dropna(subset=['parsed_date'])
        
        clean_dist['district_name'] = clean_dist['District Name'].astype(str).str.strip().str.upper()
        clean_dist['teleconsultations'] = clean_dist['Total Teleconsultations'].fillna(0).astype(int)
        clean_dist['abha_esanjivani'] = clean_dist['Total ABHA created (Esanjeevani Report)'].fillna(0).astype(int)
        clean_dist['abha_abdm'] = clean_dist['Total ABHA created (ABDM Insights)'].fillna(0).astype(int)
        clean_dist['abha_tc'] = clean_dist['Total Abha Based Teleconsultation'].fillna(0).astype(int)
        clean_dist['ehr_generated'] = clean_dist['Total EHR Generated'].fillna(0).astype(int)
        self.df_dist = clean_dist.sort_values(['parsed_date', 'district_name']).reset_index(drop=True)

    def get_available_dates(self):
        dates = self.df_up['parsed_date'].dt.strftime('%Y-%m-%d').tolist()
        return sorted(list(set(dates)), reverse=True)

    def get_summary_kpis(self, date_str: str):
        target_date = pd.to_datetime(date_str)
        day_row = self.df_up[self.df_up['parsed_date'] == target_date]
        if day_row.empty:
            return None

        prior_dates = self.df_up[self.df_up['parsed_date'] < target_date]['parsed_date']
        prev_row = None
        if not prior_dates.empty:
            prev_date = prior_dates.max()
            prev_row = self.df_up[self.df_up['parsed_date'] == prev_date].iloc[0]

        curr = day_row.iloc[0]
        curr_tc = int(curr['teleconsultations'])
        prev_tc = int(prev_row['teleconsultations']) if prev_row is not None else 0
        
        pct_change = None
        if prev_row is not None and prev_tc > 0:
            pct_change = round(((curr_tc - prev_tc) / prev_tc) * 100, 2)

        cum_tc_calc = int(self.df_up[self.df_up['parsed_date'] <= target_date]['teleconsultations'].sum())
        dist_active = self.df_dist[self.df_dist['parsed_date'] == target_date]

        return {
            "date": date_str,
            "daily_teleconsultations": curr_tc,
            "previous_day_teleconsultations": prev_tc,
            "pct_change": pct_change,
            "cumulative_teleconsultations": cum_tc_calc,
            "daily_abha_abdm": int(curr['abha_abdm']),
            "daily_abha_tc": int(curr['abha_tc']),
            "daily_ehr": int(curr['ehr_generated']),
            "cumulative_abha": int(curr['cum_abha']),
            "cumulative_ehr": int(curr['cum_ehr']),
            "active_districts": int(len(dist_active)),
            "total_districts": 75,
            "coverage_pct": round((len(dist_active) / 75.0) * 100, 1)
        }

    def get_district_performance(self, date_str: str):
        target_date = pd.to_datetime(date_str)
        subset = self.df_dist[self.df_dist['parsed_date'] == target_date].copy()
        subset = subset.sort_values('teleconsultations', ascending=False)
        return subset[['district_name', 'teleconsultations', 'abha_tc', 'ehr_generated']].to_dict(orient='records')

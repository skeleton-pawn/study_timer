from flask import Flask, render_template, request, jsonify
import gspread
import time
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open("StopwatchData").sheet1

SUBJECTS = ["원가", "세법", "재정", "행정", "세회", "재무", "독서", "craft"]

def get_custom_date():
    """3AM 기준으로 날짜 계산"""
    now = datetime.now()
    if now.hour < 3:
        return (now - timedelta(days=1)).strftime('%Y-%m-%d')
    return now.strftime('%Y-%m-%d')

def ensure_header_exists():
    """시트 헤더 확인 및 생성"""
    try:
        headers = sheet.row_values(1)
        if not headers or len(headers) != 5:
            sheet.clear()
            sheet.append_row(["Date", "Subject", "Start Time", "End Time", "Duration"])
    except:
        sheet.clear()
        sheet.append_row(["Date", "Subject", "Start Time", "End Time", "Duration"])

# 앱 시작시 헤더 확인
ensure_header_exists()

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')

@app.route('/api/subjects')
def get_subjects():
    """과목 목록 반환"""
    return jsonify(SUBJECTS)

@app.route('/api/today-stats')
def get_today_stats():
    """오늘 공부 통계"""
    try:
        today_date = get_custom_date()
        all_data = sheet.get_all_records()
        today_data = [record for record in all_data if record.get('Date', '') == today_date]
        
        # 총 공부시간
        total_seconds = sum(record.get('Duration', 0) for record in today_data)
        total_hours = total_seconds / 3600
        
        # 과목별 공부시간
        subject_times = {}
        for subject in SUBJECTS:
            subject_seconds = sum(record.get('Duration', 0) for record in today_data 
                                if record.get('Subject', '') == subject)
            if subject_seconds > 0:
                subject_times[subject] = {
                    'minutes': subject_seconds / 60,
                    'hours': subject_seconds / 3600
                }
        
        return jsonify({
            'date': today_date,
            'total_hours': round(total_hours, 2),
            'subject_times': subject_times,
            'current_time': datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/record-session', methods=['POST'])
def record_session():
    """공부 세션 기록"""
    try:
        data = request.json
        subject = data.get('subject')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        duration = data.get('duration')
        
        # 60초 미만은 기록하지 않음
        if duration < 60:
            return jsonify({'message': 'Session too short, not recorded'}), 400
        
        # Google Sheets에 기록
        start_str = datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')
        end_str = datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')
        custom_date = get_custom_date()
        
        sheet.append_row([custom_date, subject, start_str, end_str, duration])
        
        return jsonify({
            'message': 'Session recorded successfully',
            'duration_minutes': round(duration / 60, 2)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/statistics/<int:days>')
def get_statistics(days):
    """기간별 통계"""
    try:
        all_data = sheet.get_all_records()
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        recent_data = [r for r in all_data if r.get('Date', '') >= cutoff_date]
        
        # 총 공부시간
        total_time = sum(r.get('Duration', 0) for r in recent_data)
        
        # 과목별 공부시간
        subject_times = {}
        for subject in SUBJECTS:
            subject_duration = sum(r.get('Duration', 0) for r in recent_data 
                                 if r.get('Subject', '') == subject)
            if subject_duration > 0:
                subject_times[subject] = {
                    'minutes': round(subject_duration / 60, 2),
                    'hours': round(subject_duration / 3600, 2)
                }
        
        # 일별 공부시간
        daily_stats = {}
        for record in recent_data:
            date = record.get('Date', '')
            if date not in daily_stats:
                daily_stats[date] = 0
            daily_stats[date] += record.get('Duration', 0)
        
        # 일별 통계를 시간 단위로 변환
        for date in daily_stats:
            daily_stats[date] = round(daily_stats[date] / 3600, 2)
        
        return jsonify({
            'days': days,
            'total_minutes': round(total_time / 60, 2),
            'total_hours': round(total_time / 3600, 2),
            'average_hours_per_day': round(total_time / 3600 / days, 2),
            'subject_times': subject_times,
            'daily_stats': daily_stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/subject-comparison')
def get_subject_comparison():
    """과목별 비교 통계 (3일, 7일, 14일, 30일)"""
    try:
        all_data = sheet.get_all_records()
        periods = [3, 7, 14, 30]
        comparison_data = {}
        
        for days in periods:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            recent_data = [r for r in all_data if r.get('Date', '') >= cutoff_date]
            
            period_stats = {}
            total_time = 0
            
            for subject in SUBJECTS:
                subject_duration = sum(r.get('Duration', 0) for r in recent_data 
                                     if r.get('Subject', '') == subject)
                if subject_duration > 0:
                    period_stats[subject] = {
                        'minutes': round(subject_duration / 60, 2),
                        'hours': round(subject_duration / 3600, 2),
                        'seconds': subject_duration
                    }
                    total_time += subject_duration
                else:
                    period_stats[subject] = {
                        'minutes': 0,
                        'hours': 0,
                        'seconds': 0
                    }
            
            comparison_data[f'{days}days'] = {
                'total_hours': round(total_time / 3600, 2),
                'average_per_day': round(total_time / 3600 / days, 2),
                'subjects': period_stats
            }
        
        return jsonify(comparison_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health_check():
    """서버 상태 확인"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
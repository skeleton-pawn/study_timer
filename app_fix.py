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
    except gspread.exceptions.APIError: # 좀 더 구체적인 예외 처리
        # 시트가 비어있거나 접근 오류 시 헤더 생성
        sheet.clear()
        sheet.append_row(["Date", "Subject", "Start Time", "End Time", "Duration"])
    except Exception:
        # 기타 예외 상황
        sheet.clear()
        sheet.append_row(["Date", "Subject", "Start Time", "End Time", "Duration"])


# 앱 시작시 헤더 확인
ensure_header_exists()

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')

@app.route('/stopwatches')
def multi_stopwatch_page():
    """40개의 멀티 스톱워치 페이지를 렌더링합니다."""
    return render_template('multi.html')

@app.route('/api/subjects')
def get_subjects():
    """과목 목록 반환"""
    return jsonify(SUBJECTS)

@app.route('/api/today-stats')
def get_today_stats():
    """오늘 공부 통계 (동기부여 메시지 포함)"""
    try:
        today_date = get_custom_date()
        yesterday_date = get_yesterday_date()
        
        all_data = sheet.get_all_records()
        
        today_data = [record for record in all_data if record.get('Date', '') == today_date]
        yesterday_data = [record for record in all_data if record.get('Date', '') == yesterday_date]

        # 총 공부시간 오늘
        today_total_seconds = sum(record.get('Duration', 0) for record in today_data)
        today_total_hours = today_total_seconds / 3600

        # 총 공부시간 어제
        yesterday_total_seconds = sum(record.get('Duration', 0) for record in yesterday_data)
        yesterday_total_hours = yesterday_total_seconds / 3600
        
        # 동기부여 메시지
        motivation_message = get_motivation_message(today_total_hours, yesterday_total_hours)
        
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
        
        response_data = {
            'date': today_date,
            'total_hours': round(today_total_hours, 2),
            'subject_times': subject_times,
            'current_time': datetime.now().strftime('%H:%M:%S')
        }
        # 동기부여 메시지가 있을 때만 응답에 포함
        if motivation_message:
            response_data['motivation_message'] = motivation_message

        return jsonify(response_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# /api/today-stats 라우트 위에 추가할 헬퍼 함수들
def get_yesterday_date():
    """어제 날짜 계산 (3AM 기준)"""
    now = datetime.now()
    if now.hour < 3:
        # 현재 시간이 3시 이전이면 '오늘'은 어제 날짜이므로, '어제'는 이틀 전 날짜가 됨
        return (now - timedelta(days=2)).strftime('%Y-%m-%d')
    else:
        # 현재 시간이 3시 이후면 '오늘'은 오늘 날짜이므로, '어제'는 어제 날짜가 됨
        return (now - timedelta(days=1)).strftime('%Y-%m-%d')

def get_motivation_message(today_hours, yesterday_hours):
    """동기부여 메시지 생성 (요청대로 '같은 페이스' 메시지 제외)"""
    # 어제 기록이 없거나 0시간인 경우
    if yesterday_hours == 0:
        if today_hours > 0:
            return "새로운 시작이네요! 오늘도 화이팅! 🌟"
        else:
            return "오늘부터 시작해보세요! 💪"
    
    # 어제와 오늘 비교
    if today_hours > yesterday_hours:
        improvement = today_hours - yesterday_hours
        return f"어제의 나를 넘어서고 있습니다! (+{improvement:.1f}시간) 🎉"
    elif today_hours < yesterday_hours:
        gap = yesterday_hours - today_hours
        return f"이길 수 있어요 힘내요! (어제보다 -{gap:.1f}시간) 💪"
    
    # 그 외의 경우 (오늘과 어제 공부 시간이 같은 경우) 메시지를 반환하지 않음
    return None

# === START: 수정된 record_session 함수 ===
@app.route('/api/record-session', methods=['POST'])
def record_session():
    """공부 세션 기록"""
    data = request.json
    subject = data.get('subject')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    duration = data.get('duration')
        
    # 60초 미만은 기록하지 않음
    if duration < 60:
        return jsonify({'message': 'Session too short, not recorded'}), 400
        
    # Google Sheets에 기록할 데이터 미리 준비
    start_str = datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')
    end_str = datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')
    custom_date = get_custom_date()
    
    try:
        # Google Sheets에 기록 시도
        sheet.append_row([custom_date, subject, start_str, end_str, int(duration)])
        
        return jsonify({
            'message': 'Session recorded successfully',
            'duration_minutes': round(duration / 60, 2)
        })
    except Exception as e:
        # 기록 실패 시, 수동 업데이트를 위한 정보를 포함하여 에러 응답 반환
        manual_update_info = {
            "date": custom_date,
            "subject": subject,
            "start_time_str": start_str,
            "end_time_str": end_str,
            "duration_seconds": int(duration)
        }
        
        return jsonify({
            'error': 'Google Sheets 기록에 실패했습니다. 아래 정보를 수동으로 업데이트해주세요.',
            'details': str(e), # 실제 에러 원인 (디버깅용)
            'manual_update_info': manual_update_info
        }), 500
# === END: 수정된 record_session 함수 ===


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
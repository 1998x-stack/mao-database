"""
Date resolver module for 毛泽东年谱.epub

Handles:
- Regex-based parsing of date_raw into structured fields
- State machine for relative dates (同日, 同月, 同旬, 同季)
- Date ranges, lists, and fuzzy dates
- Season and period markers
"""

import re
from typing import Optional, Dict, Any, Tuple, List


# --- Regex Patterns ---

# Full date: 4月14日
RE_FULL_DATE = re.compile(r'(\d{1,2})月(\d{1,2})日')

# Month only: 4月
RE_MONTH_ONLY = re.compile(r'^(\d{1,2})月$')

# Period: 6月下旬, 6月上中旬, 10月中下旬
RE_PERIOD = re.compile(r'(\d{1,2})月(上旬|中旬|下旬|初|底|上中旬|中下旬|上半月|下半月)')

# Season: 春, 夏, 秋, 冬, 春夏间, 夏秋间, 夏初
RE_SEASON = re.compile(r'^(春|夏|秋|冬|春夏间|夏秋间|夏初|夏秋)$')

# Season with year: 1937年冬
RE_SEASON_YEAR = re.compile(r'(\d{4})年(春|夏|秋|冬)')

# Season with "本年": 本年冬
RE_SEASON_BENNIAN = re.compile(r'本年(春|夏|秋|冬)')

# Year marker: 本年, 本月, 本学期末
RE_YEAR_ONLY = re.compile(r'^(本年|本月|本学期末|上半年|学期末|暑假|开学后)$')

# Relative: 同日, 同月, 同旬, 同季
RE_RELATIVE = re.compile(r'^(同日|同月|同旬|同季)$')

# Date range with em-dash: 1月11日—22日, 2月27日—3月1日
RE_RANGE = re.compile(r'(\d{1,2}月\d{1,2}日?)[—一](\d{1,2}月?\d{0,2}日?)')

# Comma-separated dates: 11月29日、30日
RE_LIST = re.compile(r'(?:\d{1,2}月\d{1,2}日[、，]?)+')

# Fuzzy: 前后, 左右, 或
RE_FUZZY = re.compile(r'[前后左右或]')

# Non-standard: 7月、8月 (month list)
RE_MONTH_LIST = re.compile(r'(\d{1,2})月[、，](\d{1,2})月')

# Month range: 10月—12月
RE_MONTH_RANGE = re.compile(r'(\d{1,2})月[—一](\d{1,2})月')

# 11月底（或12月初）
RE_FUZZY_MONTH = re.compile(r'(\d{1,2})月底[（(]或(\d{1,2})月初[）)]')


def resolve_date(date_raw: str, file_year: int,
                 prev_resolved: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Resolve a raw date string into structured fields.

    Args:
        date_raw: The raw date text from the EPUB bold span
        file_year: The year from the h1 heading
        prev_resolved: The resolved fields of the previous entry (for 同日 resolution)

    Returns:
        Dict with year, month, day, season, etc.
    """
    date_raw = date_raw.strip()

    # --- Relative dates (need previous entry) ---
    if RE_RELATIVE.match(date_raw):
        marker = RE_RELATIVE.match(date_raw).group(1)
        result = _build_relative(date_raw, file_year, marker, prev_resolved)
        return result

    # --- Year-only markers ---
    if RE_YEAR_ONLY.match(date_raw):
        return {
            'year': file_year,
            'month': None,
            'day': None,
            'season': None,
            'ten_day_period': None,
            'date_type': 'year_only',
            'date_display': f'{file_year}年',
            'is_same_day': False,
            'is_approximate': False,
            'date_end': None,
            'date_list': None,
            'fuzzy_modifier': None,
        }

    # --- Season with year ---
    season_year_match = RE_SEASON_YEAR.match(date_raw)
    if season_year_match:
        s_year = int(season_year_match.group(1))
        season = season_year_match.group(2)
        return {
            'year': s_year,
            'month': None,
            'day': None,
            'season': season,
            'ten_day_period': None,
            'date_type': 'season',
            'date_display': f'{s_year}年{season}',
            'is_same_day': False,
            'is_approximate': False,
            'date_end': None,
            'date_list': None,
            'fuzzy_modifier': None,
        }

    # --- Fuzzy month boundary ---
    fuzzy_month = RE_FUZZY_MONTH.match(date_raw)
    if fuzzy_month:
        m1 = int(fuzzy_month.group(1))
        m2 = int(fuzzy_month.group(2))
        return {
            'year': file_year,
            'month': m1,
            'day': None,
            'season': None,
            'ten_day_period': '底',
            'date_type': 'fuzzy',
            'date_display': f'{file_year}年{m1}月底（或{m2}月初）',
            'is_same_day': False,
            'is_approximate': True,
            'date_end': {'year': file_year, 'month': m2, 'day': None},
            'date_list': None,
            'fuzzy_modifier': '或',
        }

    # --- Date ranges (must check before simple patterns) ---
    range_match = RE_RANGE.search(date_raw)
    if range_match:
        return _resolve_range(date_raw, file_year, range_match)

    # --- Comma-separated date lists ---
    if '、' in date_raw and '月' in date_raw:
        return _resolve_list(date_raw, file_year)

    # --- Month range ---
    month_range = RE_MONTH_RANGE.match(date_raw)
    if month_range:
        m1 = int(month_range.group(1))
        m2 = int(month_range.group(2))
        return {
            'year': file_year,
            'month': m1,
            'day': None,
            'season': None,
            'ten_day_period': None,
            'date_type': 'range',
            'date_display': f'{file_year}年{m1}月—{m2}月',
            'is_same_day': False,
            'is_approximate': False,
            'date_end': {'year': file_year, 'month': m2, 'day': None},
            'date_list': None,
            'fuzzy_modifier': None,
        }

    # --- Full date ---
    full_match = RE_FULL_DATE.search(date_raw)
    if full_match:
        month = int(full_match.group(1))
        day = int(full_match.group(2))
        return {
            'year': file_year,
            'month': month,
            'day': day,
            'season': None,
            'ten_day_period': None,
            'date_type': 'full',
            'date_display': f'{file_year}年{month}月{day}日',
            'is_same_day': False,
            'is_approximate': _has_fuzzy(date_raw),
            'date_end': None,
            'date_list': None,
            'fuzzy_modifier': _fuzzy_modifier(date_raw) if _has_fuzzy(date_raw) else None,
        }

    # --- Period (旬/初/底) ---
    period_match = RE_PERIOD.match(date_raw)
    if period_match:
        month = int(period_match.group(1))
        period = period_match.group(2)
        return {
            'year': file_year,
            'month': month,
            'day': None,
            'season': None,
            'ten_day_period': period,
            'date_type': 'period',
            'date_display': f'{file_year}年{month}月{period}',
            'is_same_day': False,
            'is_approximate': False,
            'date_end': None,
            'date_list': None,
            'fuzzy_modifier': None,
        }

    # --- Month only ---
    month_only = RE_MONTH_ONLY.match(date_raw)
    if month_only:
        month = int(month_only.group(1))
        return {
            'year': file_year,
            'month': month,
            'day': None,
            'season': None,
            'ten_day_period': None,
            'date_type': 'month',
            'date_display': f'{file_year}年{month}月',
            'is_same_day': False,
            'is_approximate': False,
            'date_end': None,
            'date_list': None,
            'fuzzy_modifier': None,
        }

    # --- Season only ---
    season_match = RE_SEASON.match(date_raw)
    if season_match:
        season = season_match.group(1)
        return {
            'year': file_year,
            'month': None,
            'day': None,
            'season': season,
            'ten_day_period': None,
            'date_type': 'season',
            'date_display': f'{file_year}年{season}',
            'is_same_day': False,
            'is_approximate': False,
            'date_end': None,
            'date_list': None,
            'fuzzy_modifier': None,
        }

    # --- Fallback: unrecognized ---
    return {
        'year': file_year,
        'month': None,
        'day': None,
        'season': None,
        'ten_day_period': None,
        'date_type': 'year_only',
        'date_display': f'{file_year}年',
        'is_same_day': False,
        'is_approximate': True,
        'date_end': None,
        'date_list': None,
        'fuzzy_modifier': None,
    }


def _build_relative(date_raw: str, file_year: int, marker: str,
                    prev: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Build resolved fields for relative dates (同日 etc.)"""
    if prev is None:
        # No previous entry — can't resolve
        return {
            'year': file_year,
            'month': None,
            'day': None,
            'season': None,
            'ten_day_period': None,
            'date_type': 'relative',
            'date_display': date_raw,
            'is_same_day': True if marker == '同日' else False,
            'is_approximate': True,
            'date_end': None,
            'date_list': None,
            'fuzzy_modifier': None,
        }

    result = {
        'year': prev.get('year', file_year),
        'month': prev.get('month'),
        'day': prev.get('day') if marker in ('同日',) else prev.get('day'),
        'season': prev.get('season'),
        'ten_day_period': prev.get('ten_day_period') if marker in ('同旬',) else prev.get('ten_day_period'),
        'date_type': 'relative',
        'date_display': prev.get('date_display', f'{file_year}年'),
        'is_same_day': marker == '同日',
        'is_approximate': False,
        'date_end': None,
        'date_list': None,
        'fuzzy_modifier': None,
    }

    # For 同月: only keep month-level info
    if marker == '同月':
        result['day'] = None
        result['ten_day_period'] = None

    return result


def _resolve_range(date_raw: str, file_year: int,
                   range_match: re.Match) -> Dict[str, Any]:
    """Resolve a date range like '1月11日—22日' or '2月27日—3月1日'."""
    start_str = range_match.group(1)
    end_str = range_match.group(2)

    # Parse start
    start_full = RE_FULL_DATE.search(start_str)
    if start_full:
        start_month = int(start_full.group(1))
        start_day = int(start_full.group(2))
    else:
        start_month_match = RE_MONTH_ONLY.search(start_str)
        if start_month_match:
            start_month = int(start_month_match.group(1))
            start_day = None
        else:
            start_month = None
            start_day = None

    # Parse end
    end_full = RE_FULL_DATE.search(end_str)
    if end_full:
        end_month = int(end_full.group(1))
        end_day = int(end_full.group(2))
    else:
        # Might be "22日" (same month) or "8月初"
        end_day_only = re.search(r'(\d{1,2})日', end_str)
        if end_day_only:
            end_month = start_month  # inherit from start
            end_day = int(end_day_only.group(1))
        else:
            end_month = None
            end_day = None

    date_display = f'{file_year}年{date_raw.replace("一", "—")}'

    return {
        'year': file_year,
        'month': start_month,
        'day': start_day,
        'season': None,
        'ten_day_period': None,
        'date_type': 'range',
        'date_display': date_display,
        'is_same_day': False,
        'is_approximate': False,
        'date_end': {
            'year': file_year,
            'month': end_month,
            'day': end_day,
        },
        'date_list': None,
        'fuzzy_modifier': None,
    }


def _resolve_list(date_raw: str, file_year: int) -> Dict[str, Any]:
    """Resolve a comma-separated date list like '11月29日、30日'."""
    # Extract all date components
    parts = re.findall(r'(\d{1,2}月\d{1,2}日)', date_raw)
    date_list = []
    for part in parts:
        m = RE_FULL_DATE.match(part)
        if m:
            month = int(m.group(1))
            day = int(m.group(2))
            date_list.append(f'{file_year}-{month:02d}-{day:02d}')

    # First date becomes the primary resolved date
    first_date = date_list[0] if date_list else ''
    first_parts = first_date.split('-') if first_date else []
    first_month = int(first_parts[1]) if len(first_parts) > 1 else None
    first_day = int(first_parts[2]) if len(first_parts) > 2 else None

    return {
        'year': file_year,
        'month': first_month,
        'day': first_day,
        'season': None,
        'ten_day_period': None,
        'date_type': 'list',
        'date_display': f'{file_year}年{date_raw}',
        'is_same_day': False,
        'is_approximate': False,
        'date_end': None,
        'date_list': date_list if len(date_list) > 1 else None,
        'fuzzy_modifier': None,
    }


def _has_fuzzy(date_raw: str) -> bool:
    """Check if date_raw contains fuzzy markers."""
    return bool(RE_FUZZY.search(date_raw))


def _fuzzy_modifier(date_raw: str) -> Optional[str]:
    """Extract fuzzy modifier from date_raw."""
    if '前后' in date_raw:
        return '前后'
    if '左右' in date_raw:
        return '左右'
    if '或' in date_raw:
        return '或'
    if '以前' in date_raw:
        return '以前'
    if re.search(r'(?<!以)前', date_raw):
        return '前'
    return None

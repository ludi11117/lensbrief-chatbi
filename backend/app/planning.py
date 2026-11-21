import re
from calendar import monthrange
from datetime import date, timedelta
from unicodedata import normalize

METRICS = {
    "gmv": r"销售额|成交额|gmv",
    "orders": r"订单量|订单数|支付订单(?:量|数)?",
    "refund_rate": r"退款率",
}
DIMENSIONS = {
    "channel": r"渠道|成交来源",
    "product": r"产品|机型|型号",
    "day": r"按日|按日期|每日|每天|逐日|日趋势",
    "department": r"部门|团队",
}
MONTH_NAMES = ("一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二")
MONTHS = re.compile(r"(?<!\d)(?:(\d{4})\s*年\s*)?(\d{1,2}|十[一二]?|[一二三四五六七八九])\s*月")
ISO_DATE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
FOLLOW_UP = re.compile(r"^(?:那|然后)?(?:改成|改为|改按|改看|换成|换为|换按|再看|继续看|沿用)")
UNSUPPORTED = re.compile(
    r"同比|环比|增长率|增幅|利润|净收入|成本|退款数|退款额|客单价|用户数|占比|排行前|top\s*\d|"
    r"最近|过去|昨天|前天|今天|本月|上月|上个月|下月|本周|上周|下周|今年|去年|季度|"
    r"华[东南北中]|海外|全国|北京|上海|深圳|官网|电商平台|线下零售|trail x|pocket air|orbit mini|"
    r"全部范围|全量|所有区域|只看|仅看|排除|筛选|过滤|大于|小于|高于|低于|多少用户"
)

class PlanError(ValueError):
    pass

def choose(text, choices, label):
    matches = [code for code, pattern in choices.items() if re.search(pattern, text)]
    if len(matches) > 1:
        raise PlanError(f"请在一个问题中指定一种{label}。")
    return matches[0] if matches else None

def requested_window(text, anchor):
    iso = list(ISO_DATE.finditer(text))
    months = list(MONTHS.finditer(text))
    if iso:
        if months or len(iso) > 2:
            raise PlanError("请指定一个连续的查询日期区间。")
        if len(iso) == 2 and not re.fullmatch(r"\s*(?:至|到|~|—|–|-)\s*", text[iso[0].end():iso[1].start()]):
            raise PlanError("请用“至”连接两个日期。")
        try:
            return tuple(date.fromisoformat(match[0]) for match in (iso[0], iso[-1])), None
        except ValueError:
            raise PlanError("请输入有效日期，格式为 YYYY-MM-DD。") from None
    if months:
        if len(months) > 1 or re.search(r"\d+\s*[日号]", text):
            raise PlanError("月份查询只支持单月；具体日期区间请使用 YYYY-MM-DD 至 YYYY-MM-DD。")
        year_text, month_text = months[0].groups()
        if not year_text and anchor is None:
            raise PlanError("请在月份前注明四位年份。")
        year = int(year_text) if year_text else anchor.year
        month = int(month_text) if month_text.isdecimal() else MONTH_NAMES.index(month_text) + 1
        try:
            return (date(year, month, 1), date(year, month, monthrange(year, month)[1])), (
                None if year_text else f"未指定年份，使用 {year} 年。"
            )
        except ValueError:
            raise PlanError("请输入有效的年份和月份。") from None
    if re.search(r"\d{4}\s*[-年]|\d+\s*[日号]|周|月初|月末", text):
        raise PlanError("请使用整月或 YYYY-MM-DD 格式指定日期。")
    return None, None

def resolve_question(question, available_window, previous):
    text = normalize("NFKC", question).strip().lower()
    if UNSUPPORTED.search(text):
        raise PlanError("目前支持单指标分组与单个日期区间。请用如“2026年10月按渠道看销售额”的方式提问。")
    follow_up = bool(FOLLOW_UP.match(text))
    if follow_up and previous is None:
        raise PlanError("这个上下文还没有可沿用的查询。请先明确指标和分组维度。")
    metric = choose(text, METRICS, "指标")
    dimension = choose(text, DIMENSIONS, "分组维度")
    anchor = date.fromisoformat(previous["end"]) if follow_up else available_window[1]
    window, note = requested_window(text, anchor)
    if follow_up and not (metric or dimension or window):
        raise PlanError("请指出要调整的指标、维度或日期。")
    inherited = []
    if follow_up:
        if metric is None:
            metric = previous["metric"]
            inherited.append("指标")
        if dimension is None:
            dimension = previous["dimension"]
            inherited.append("维度")
        if window is None:
            window = (date.fromisoformat(previous["start"]), date.fromisoformat(previous["end"]))
            inherited.append("日期")
    if metric is None or dimension is None:
        raise PlanError("请明确指标和分组维度，例如“按渠道看销售额”或“按产品看退款率”。")

    notes = [note] if note else []
    if inherited:
        notes.append(f"沿用本上下文最近一次成功查询的{'、'.join(inherited)}。")
    if window is None:
        start, end = available_window
        if start is None or end is None:
            raise PlanError("当前数据范围内没有可用日期，请在问题中注明日期。")
        window = (max(start, end - timedelta(days=min(29, (end - start).days))), end)
        notes.append("未指定日期，使用当前权限范围内最近最多 30 个自然日。")
    if window[0] > window[1] or (window[1] - window[0]).days > 365:
        raise PlanError("日期范围需正向且最多覆盖 366 天。")
    start, end = available_window
    if start is not None and (window[1] < start or window[0] > end):
        notes.append("所选日期与当前可用数据范围无交集，查询可能为空。")
    return {"metric": metric, "dimension": dimension, "start": window[0], "end": window[1], "notes": notes}

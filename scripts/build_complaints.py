"""Merge curated complaint research without changing legacy cases or ratings.

Inputs live in research/complaints. metadata.json is an optional JSON object;
the three audit arrays and gov-{queries,observations,cases}.json are required.
gov-cases accepts either a flat array with agencyId or an agencyId -> array map.
Run with --check to validate/build in memory without writing any output.
"""

import argparse
import copy
import csv
import io
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_AGENCIES = 125
EXPECTED_GOV_QUERIES = 131
PLATFORM_IDS = {"agency-55", "agency-56"}
PORTAL = "https://tsgs.12315.cn/#/viewport"
CSV_COLUMNS = (
    "投诉/消保补查结论",
    "12315官方公示核查",
    "投诉核查记录与来源",
)
CANDIDATE_NOTE = (
    "queries.resultUrls仅为搜索返回的候选链接，可能含无关、同名或未回读页面；"
    "不自动视为采信来源，不据此生成案例或评价。案例读取及归属边界以cases为准。"
)
GOV_LIMIT = (
    "以上数量是所列查询关键词此次匹配的公示记录数，可能含分支、近名和不同服务工种；"
    "不同查询之间可能重叠，不合计为机构投诉总数，不是投诉率或质量排名。"
    "公示期限为一年，不涵盖全部历史、未公开投诉或所有分支。"
    "投诉内容为当事人填写，调解结果不是违法认定；达成调解不等于退款已到账。"
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def source_key(case, agency_id, government=False):
    """Identity, not an evidence-quality assessment; portal records need a date."""
    if government:
        published = str(case.get("published", "")).strip()
        require(published, f"{agency_id}: government case lacks published time")
        return f"gov:{agency_id}:{published}"
    url = str(case.get("url", "")).strip()
    require(url, f"{agency_id}: case lacks source URL")
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    path = unquote(parts.path).rstrip("/")
    if any(host == domain or host.endswith("." + domain)
           for domain in ("tousu.sina.com.cn", "tousu.sina.cn")):
        match = re.search(r"/complaint/view/(\d+)(?:/|$)", path)
        if match:
            return "blackcat:" + match.group(1)
    if any(host == domain or host.endswith("." + domain)
           for domain in ("xfb315.com", "xfb365.com")):
        match = re.search(r"/tousu/(\d+)(?:/|$)", path)
        if match:
            return "xfb:" + match.group(1)
    # Strip tracking/query/fragment and decode the path, preserving the source host.
    return "url:" + urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def legacy_alias(key):
    """Only documented URL presentation variants; never fuzzy-match case text."""
    if key.startswith("url:"):
        parts = urlsplit(key[4:])
        if parts.hostname == "zh.wikisource.org":
            path = re.sub(r"^/(?:wiki|zh-hans|zh-hant|zh-cn|zh-tw)/", "/wiki/", parts.path)
            return urlunsplit((parts.scheme, parts.netloc, path, "", ""))
        if parts.hostname in {"m.bjnews.com.cn", "www.bjnews.com.cn"}:
            return urlunsplit((parts.scheme, "www.bjnews.com.cn", parts.path, "", ""))
    return key


class CaseIds:
    """Annotate new audit cases while leaving item.cases byte-for-byte values alone."""

    def __init__(self, item):
        self.agency_id = item["id"]
        self.legacy_by_id = {}
        self.legacy_by_key = {}
        self.legacy_by_alias = defaultdict(list)
        self.assigned = {}
        self.used_ids = set()
        self.next_number = 1
        for old in item.get("cases", []):
            identifier = old.get("id")
            if identifier:
                require(identifier not in self.legacy_by_id,
                        f"{self.agency_id}: duplicate legacy case ID {identifier}")
                self.legacy_by_id[identifier] = old
                self.used_ids.add(identifier)
            if old.get("url"):
                key = source_key(old, self.agency_id)
                self.legacy_by_key.setdefault(key, old)
                self.legacy_by_alias[legacy_alias(key)].append(old)
        # Reuse generated IDs on subsequent runs even if curated input order changes.
        prefix = f"C-{self.agency_id}-"
        for audit_name in ("complaintAudit", "governmentAudit"):
            for old in item.get(audit_name, {}).get("cases", []):
                key, identifier = old.get("sourceKey"), old.get("id")
                if key and identifier:
                    self.assigned[key] = identifier
                    self.used_ids.add(identifier)
                    if identifier.startswith(prefix) and identifier[len(prefix):].isdigit():
                        self.next_number = max(self.next_number, int(identifier[len(prefix):]) + 1)

    def annotate(self, incoming, government=False):
        case = copy.deepcopy(incoming)
        key = source_key(case, self.agency_id, government)
        old = None
        explicit = case.get("existingCaseId")
        if explicit:
            require(explicit in self.legacy_by_id,
                    f"{self.agency_id}: unknown existingCaseId {explicit}")
            old = self.legacy_by_id[explicit]
        elif not government:
            old = self.legacy_by_key.get(key)
            if old is None:
                alternatives = self.legacy_by_alias.get(legacy_alias(key), [])
                if len(alternatives) == 1:
                    old = alternatives[0]
        if old is not None and old.get("id"):
            identifier = old["id"]
            case["existingCaseId"] = identifier
            # Inherit the legacy identity for mobile/desktop or language-path variants.
            if not government and old.get("url"):
                key = source_key(old, self.agency_id)
        elif key in self.assigned:
            identifier = self.assigned[key]
        else:
            identifier = f"C-{self.agency_id}-{self.next_number:03d}"
            while identifier in self.used_ids:
                self.next_number += 1
                identifier = f"C-{self.agency_id}-{self.next_number:03d}"
            self.next_number += 1
        self.assigned[key] = identifier
        self.used_ids.add(identifier)
        case.update(id=identifier, sourceKey=key, complaintUpdate=True)
        return case


def annotate_cases(cases, ids, government=False):
    require(isinstance(cases, list), f"{ids.agency_id}: cases must be an array")
    result = []
    positions = {}
    for incoming in cases:
        case = ids.annotate(incoming, government)
        key = case["sourceKey"]
        if key in positions:
            previous = result[positions[key]]
            # Duplicate URLs must not silently discard a different outcome or context.
            for field in ("summary", "response", "resolution", "limits", "job", "city"):
                require(not previous.get(field) or not case.get(field)
                        or previous[field] == case[field],
                        f"{ids.agency_id}: conflicting duplicate {key}, field {field}")
            previous.update({k: v for k, v in case.items() if v not in (None, "", [])})
        else:
            positions[key] = len(result)
            result.append(case)
    return result


def government_cases(value):
    if isinstance(value, list):
        return copy.deepcopy(value)
    require(isinstance(value, dict), "gov-cases must be an array or agencyId map")
    result = []
    for agency_id, cases in value.items():
        require(isinstance(cases, list), f"gov-cases[{agency_id}] must be an array")
        for case in cases:
            require(case.get("agencyId", agency_id) == agency_id,
                    f"gov-cases agencyId mismatch: {agency_id}")
            result.append({**case, "agencyId": agency_id})
    return result


def gov_audit(item, queries, cases, observations, checked_at):
    annotated = []
    has_results = any(query["displayedCount"] > 0 for query in queries)
    for original in queries:
        query = copy.deepcopy(original)
        keyword = query["query"]
        count = query["displayedCount"]
        observation = observations.get(keyword, "")
        require(isinstance(observation, str), f"Observation must be text: {keyword}")
        if count:
            query["resultSummary"] = (
                f"查询“{keyword}”此次页面显示{count}条关键词匹配公示。"
                + (observation or "未取得可单列的首屏观察摘要；不能推断每条均属于该精确法人。")
                + GOV_LIMIT
            )
        else:
            query["resultSummary"] = (
                f"查询“{keyword}”：该名称在此次公示列表未见记录，"
                "不代表零投诉或没有历史纠纷；公示期限、名称别称和公开范围会影响结果。"
            )
        annotated.append(query)
    if item["id"] in PLATFORM_IDS and not queries:
        summary = (
            "该条目是多商户平台频道，未将平台作为单一家政机构查询或合并投诉。"
            "应按实际商户、合同及收款主体分别核查；没有统一可比较的机构公示数。"
        )
    else:
        if cases:
            latest = max(cases, key=lambda c: str(c.get("published", "")))
            summary = (
                f"已回读详情中最新公示（{str(latest['published']).split()[0]}）："
                f"{latest.get('company') or latest.get('query') or item['name']}，"
                f"服务类别为{latest.get('job') or '未明确'}，"
                f"处理结果为“{latest.get('resolution') or '页面未显示明确结果'}”。"
                "公示未披露协议细节及退款到账证据，不能据此推断北京育儿嫂整体服务质量。"
            )
        elif has_results:
            notes = list(dict.fromkeys(observations.get(q["query"], "")
                                       for q in queries if q["displayedCount"] > 0))
            summary = "已核对当前公示列表。" + "".join(note for note in notes if note)
            if not any(notes):
                summary += "查询名称存在匹配公示，相关记录的主体和具体服务需逐条区分。"
            summary += "名称匹配可含分支及其他工种，不能作为机构投诉率。"
        else:
            summary = (f"已按{len(queries)}组名称查询当前公示列表，本轮未见记录；"
                       "不代表零投诉，公示期限、名称别称和公开范围会影响结果。")
    return dict(checkedAt=max((str(q["checkedAt"]) for q in queries), default=checked_at),
                queries=annotated, cases=cases, summary=summary, coverageLimit=GOV_LIMIT,
                hasResults=has_results, limit=GOV_LIMIT,
                queryCount=len(annotated), detailCaseCount=len(cases))


def case_text(case):
    fields = [("案例", case.get("title") or case.get("type")),
              ("日期", case.get("date")), ("工种", case.get("job")),
              ("记录", case.get("summary")), ("回应", case.get("response")),
              ("处理结果", case.get("resolution")), ("处理部门", case.get("department")),
              ("限制", case.get("limits")), ("读取状态", case.get("readStatus")),
              ("来源", case.get("url"))]
    return "\n".join(f"{label}：{value}" for label, value in fields if value)


def download_row(item):
    web, gov = item["complaintAudit"], item["governmentAudit"]
    cases = web["cases"] + gov["cases"]
    queries = [f"[{q.get('channel', '公开检索')}] {q['query']}\n{q.get('resultSummary', '')}"
               for q in web["queries"]]
    queries += [f"[12315站内] {q['query']}\n{q['resultSummary']}" for q in gov["queries"]]
    detail = "\n\n".join(case_text(case) for case in cases) or "未取得本轮可单列案例；不代表没有投诉。"
    sources = list(dict.fromkeys(c["url"] for c in cases if c.get("url")))
    if gov["queries"] and PORTAL not in sources:
        sources.append(PORTAL)
    candidates = list(dict.fromkeys(u for q in web["queries"] for u in q.get("resultUrls", [])))
    return {
        "机构ID": item["id"], "机构/品牌": item["name"],
        CSV_COLUMNS[0]: web["summary"], CSV_COLUMNS[1]: gov["summary"],
        "实际查询词与检索结论": "\n\n".join(queries),
        "案例处理结果与边界": detail,
        "案例及官方查询来源（读取边界见记录）": "\n".join(sources),
        "搜索候选链接（不代表采信）": CANDIDATE_NOTE + "\n" + "\n".join(candidates),
        "证据截至": web.get("checkedAt", ""),
    }


def csv_text(rows, fieldnames):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def build(root=ROOT):
    research = root / "research/complaints"
    data = read_json(root / "dist/data.json")
    original = copy.deepcopy(data)
    items = data["items"]
    require(len(items) == EXPECTED_AGENCIES, "Expected 125 data items")
    known = {item["id"]: item for item in items}
    require(len(known) == EXPECTED_AGENCIES, "Duplicate data item IDs")
    audits = []
    for batch in ("01-42", "43-84", "85-125"):
        value = read_json(research / f"audit-{batch}.json")
        require(isinstance(value, list), f"audit-{batch} must be an array")
        audits.extend(value)
    require(len(audits) == EXPECTED_AGENCIES, "Expected exactly 125 complaint audits")
    indexed = {audit["id"]: audit for audit in audits}
    require(len(indexed) == EXPECTED_AGENCIES and set(indexed) == set(known),
            "Audit IDs must exactly cover all 125 data items")
    for audit in audits:
        require(isinstance(audit.get("queries"), list) and len(audit["queries"]) >= 3,
                f"{audit['id']}: at least three actual queries are required")
        require(all(isinstance(q.get("query"), str) and q["query"].strip()
                    for q in audit["queries"]), f"{audit['id']}: blank query")
        require(isinstance(audit.get("summary"), str), f"{audit['id']}: missing summary")
    metadata_path = research / "metadata.json"
    metadata = read_json(metadata_path) if metadata_path.exists() else {"checkedAt": data.get("checkedAt", "")}
    require(isinstance(metadata, dict), "metadata.json must be an object")
    observations = read_json(research / "gov-observations.json")
    require(isinstance(observations, dict), "gov-observations must map exact query names to text")
    queries = read_json(research / "gov-queries.json")
    require(isinstance(queries, list) and len(queries) == EXPECTED_GOV_QUERIES,
            "Expected 131 recorded government queries")
    q_by_id, c_by_id = defaultdict(list), defaultdict(list)
    for query in queries:
        require(query.get("agencyId") in known, "Unknown agencyId in government query")
        require(isinstance(query.get("query"), str) and query["query"].strip(), "Blank government query")
        require(type(query.get("displayedCount")) is int and query["displayedCount"] >= 0,
                f"Invalid displayedCount for {query['query']}")
        require(query.get("checkedAt") and query.get("url"), "Government query lacks date or URL")
        q_by_id[query["agencyId"]].append(query)
    require(set(q_by_id) == set(known) - PLATFORM_IDS,
            "Government queries must cover the 123 institutions; channels 55/56 are not one company")
    for case in government_cases(read_json(research / "gov-cases.json")):
        agency_id = case.get("agencyId")
        require(agency_id in known, f"Unknown government case agencyId: {agency_id}")
        require(case.get("query") in {q["query"] for q in q_by_id[agency_id]},
                f"{agency_id}: government case lacks a matching actual query")
        c_by_id[agency_id].append(case)
    for item in items:
        ids = CaseIds(item)
        audit = copy.deepcopy(indexed[item["id"]])
        audit["cases"] = annotate_cases(audit.get("cases", []), ids)
        audit["candidateLinksNote"] = CANDIDATE_NOTE
        item["complaintAudit"] = audit
        cases = annotate_cases(c_by_id[item["id"]], ids, government=True)
        item["governmentAudit"] = gov_audit(item, q_by_id[item["id"]], cases, observations,
                                             metadata.get("checkedAt", data.get("checkedAt", "")))
    data["complaintReview"] = {
        **metadata, "agencies": len(items),
        "webQueries": sum(len(audit["queries"]) for audit in audits),
        "govQueries": len(queries),
        "nativeDetailCases": sum(len(item["governmentAudit"]["cases"]) for item in items),
    }
    # Only the two new audit fields and the aggregate metadata may change.
    stripped = copy.deepcopy(data)
    for before, after in zip(original["items"], stripped["items"]):
        for key in ("complaintAudit", "governmentAudit"):
            after.pop(key, None)
            if key in before:
                after[key] = before[key]
    stripped.pop("complaintReview", None)
    if "complaintReview" in original:
        stripped["complaintReview"] = original["complaintReview"]
    require(stripped == original, "Unexpected change to original data, cases, or scores")
    downloads = [download_row(item) for item in items]
    by_name = {item["name"]: item for item in items}
    require(len(by_name) == len(items), "Research CSV requires unique institution names")
    with (root / "dist/research.csv").open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    require(len(rows) == EXPECTED_AGENCIES and
            {row.get("机构/品牌") for row in rows} == set(by_name),
            "Research CSV must cover the same 125 institutions")
    for column in CSV_COLUMNS:
        if column not in fields:
            fields.append(column)
    by_id = {row["机构ID"]: row for row in downloads}
    for row in rows:
        download = by_id[by_name[row["机构/品牌"]]["id"]]
        row[CSV_COLUMNS[0]] = download[CSV_COLUMNS[0]]
        row[CSV_COLUMNS[1]] = download[CSV_COLUMNS[1]]
        row[CSV_COLUMNS[2]] = (
            download["实际查询词与检索结论"] + "\n\n" + download["案例处理结果与边界"]
            + "\n\n来源（读取及归属边界见对应记录）：\n"
            + download["案例及官方查询来源（读取边界见记录）"]
        )
    return data, csv_text(downloads, list(downloads[0])), csv_text(rows, fields)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing dist files")
    args = parser.parse_args()
    data, complaints_csv, research_csv = build()
    if not args.check:
        # Build and validate every output first; input/validation errors never partially write.
        (ROOT / "dist/data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (ROOT / "dist/complaints.csv").write_text(complaints_csv, encoding="utf-8-sig", newline="")
        (ROOT / "dist/research.csv").write_text(research_csv, encoding="utf-8-sig", newline="")
    print(json.dumps({"written": not args.check, **{
        key: data["complaintReview"][key]
        for key in ("agencies", "webQueries", "govQueries", "nativeDetailCases")
    }}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

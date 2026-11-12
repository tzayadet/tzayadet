#!/usr/bin/env python3
"""Build self-hosted GitHub activity cards using the GitHub REST and GraphQL APIs."""
from __future__ import annotations
import datetime as dt
import html
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

USER = os.getenv("GH_USERNAME", "tzayadet")
TOKEN = os.getenv("GITHUB_TOKEN", "")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "activity"
BG, PANEL, GRID = "#070D0A", "#0D1711", "#1B3424"
GREEN, SOFT, ORANGE = "#00FF41", "#6BE58A", "#FF6B35"
TEXT, MUTED = "#D8E5DA", "#8EA395"

def api(url: str, payload: dict | None = None):
    body = None if payload is None else json.dumps(payload).encode()
    headers = {"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"tzayadet-profile-cards"}
    if TOKEN: headers["Authorization"] = f"Bearer {TOKEN}"
    if body is not None: headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode())

def esc(value):
    return html.escape(str(value), quote=True)

def repositories():
    result, page = [], 1
    while page <= 20:
        batch = api(f"https://api.github.com/users/{USER}/repos?type=owner&per_page=100&page={page}&sort=updated")
        if not isinstance(batch, list) or not batch: break
        result.extend(r for r in batch if not r.get("fork") and not r.get("private"))
        if len(batch) < 100: break
        page += 1
    return result

def languages(repos):
    totals = {}
    for repo in repos:
        try:
            data = api(f"https://api.github.com/repos/{repo['full_name']}/languages")
            for name, amount in data.items(): totals[name] = totals.get(name, 0) + int(amount)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, KeyError):
            continue
    return totals

def contributions():
    if not TOKEN: return None, {}
    query = """query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }"""
    try:
        data = api("https://api.github.com/graphql", {"query":query,"variables":{"login":USER}})
        calendar = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        days = {d["date"]:int(d["contributionCount"]) for w in calendar["weeks"] for d in w["contributionDays"]}
        return int(calendar["totalContributions"]), days
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, KeyError, TypeError):
        return None, {}

def base(width, height, title, subtitle):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">
<defs><linearGradient id="p" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{PANEL}"/><stop offset="1" stop-color="{BG}"/></linearGradient><pattern id="g" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="{GRID}" opacity=".38"/></pattern></defs>
<rect width="{width}" height="{height}" rx="14" fill="url(#p)"/><rect width="{width}" height="{height}" rx="14" fill="url(#g)"/><rect x="1" y="1" width="{width-2}" height="{height-2}" rx="13" fill="none" stroke="{GREEN}" stroke-opacity=".4"/><path d="M1 48H{width-1}" stroke="{GREEN}" stroke-opacity=".3"/>
<circle cx="22" cy="24" r="4" fill="#FF5F57"/><circle cx="37" cy="24" r="4" fill="#FEBC2E"/><circle cx="52" cy="24" r="4" fill="#28C840"/>
<text x="70" y="29" fill="{SOFT}" font-family="monospace" font-size="12" letter-spacing="1.4">{esc(title.upper())}</text><text x="{width-18}" y="29" text-anchor="end" fill="{MUTED}" font-family="monospace" font-size="10">{esc(subtitle.upper())}</text>
'''

def stats_card(repos, total):
    stars = sum(int(r.get("stargazers_count",0)) for r in repos)
    forks = sum(int(r.get("forks_count",0)) for r in repos)
    values = [("PUBLIC REPOSITORIES",f"{len(repos):,}",GREEN),("STARS EARNED",f"{stars:,}",ORANGE),("FORKS",f"{forks:,}",SOFT),("CONTRIBUTIONS · 12 MONTHS","—" if total is None else f"{total:,}",TEXT)]
    svg = base(760,236,"Repository overview",f"@{USER}")
    for (label,value,color),(x,y) in zip(values,[(34,92),(394,92),(34,174),(394,174)]):
        svg += f'<text x="{x}" y="{y}" fill="{MUTED}" font-family="monospace" font-size="11" letter-spacing="1">{esc(label)}</text><text x="{x}" y="{y+38}" fill="{color}" font-family="monospace" font-size="31" font-weight="bold">{esc(value)}</text>'
    svg += f'<text x="726" y="220" text-anchor="end" fill="{MUTED}" font-family="monospace" font-size="9">UPDATED {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M UTC}</text></svg>'
    return svg

def language_card(data):
    top = sorted(data.items(),key=lambda x:x[1],reverse=True)[:6]
    svg = base(760,280,"Language distribution","PUBLIC REPOSITORIES")
    total = sum(v for _,v in top) or 1
    if not top:
        svg += f'<text x="34" y="120" fill="{MUTED}" font-family="monospace" font-size="14">LANGUAGE DATA NOT AVAILABLE</text>'
    for i,(name,amount) in enumerate(top):
        y=84+i*29
        width=460*amount/(top[0][1] or 1)
        color=GREEN if i==0 else ORANGE if i==1 else SOFT
        svg += f'<text x="34" y="{y+8}" fill="{TEXT}" font-family="monospace" font-size="12">{esc(name)}</text><rect x="190" y="{y-3}" width="460" height="10" rx="5" fill="{GRID}"/><rect x="190" y="{y-3}" width="{width:.1f}" height="10" rx="5" fill="{color}"/><text x="700" y="{y+8}" text-anchor="end" fill="{MUTED}" font-family="monospace" font-size="11">{100*amount/total:.1f}%</text>'
    svg += '<text x="34" y="260" fill="'+MUTED+'" font-family="monospace" font-size="9">AGGREGATED BY LANGUAGE BYTES · FORKS EXCLUDED</text></svg>'
    return svg

def activity_card(days,total):
    svg=base(900,220,"Commit activity","CONTRIBUTION CALENDAR · 12 MONTHS")
    today=dt.date.today()
    start=today-dt.timedelta(days=363)
    counts=[]
    for offset in range(364):
        day=start+dt.timedelta(days=offset)
        counts.append((day,days.get(day.isoformat(),0)))
    maximum=max((n for _,n in counts),default=0)
    def shade(n):
        if n<=0:return "#122018"
        if maximum<=1 or n/maximum<.25:return "#14532D"
        if n/maximum<.5:return "#16803A"
        if n/maximum<.75:return "#20B34A"
        return GREEN
    left,top,cell,gap=70,78,10,3
    for index,(day,count) in enumerate(counts):
        x=left+(index//7)*(cell+gap)
        y=top+day.weekday()*(cell+gap)
        svg+=f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{shade(count)}"><title>{day.isoformat()}: {count} contributions</title></rect>'
    for label,weekday in [("MON",0),("WED",2),("FRI",4)]:
        svg+=f'<text x="27" y="{top+weekday*(cell+gap)+9}" fill="{MUTED}" font-family="monospace" font-size="9">{label}</text>'
    for month in range(12):
        month_day=(start.replace(day=1)+dt.timedelta(days=month*30))
        week=max(0,(month_day-start).days//7)
        if week<53:
            svg+=f'<text x="{left+week*(cell+gap)}" y="65" fill="{MUTED}" font-family="monospace" font-size="9">{month_day:%b}</text>'
    note="CONTRIBUTION DATA UNAVAILABLE" if total is None else f"{total:,} CONTRIBUTIONS IN THE LAST 12 MONTHS"
    svg+=f'<text x="70" y="198" fill="{SOFT}" font-family="monospace" font-size="11">{esc(note)}</text></svg>'
    return svg

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    repos=repositories()
    langs=languages(repos)
    total,days=contributions()
    cards={"repository-stats.svg":stats_card(repos,total),"language-distribution.svg":language_card(langs),"commit-activity.svg":activity_card(days,total)}
    for filename,content in cards.items():
        (OUT/filename).write_text(content,encoding="utf-8")
        print(f"Generated {filename}")
    print(f"Repositories={len(repos)} Languages={len(langs)} Contributions={total}")

if __name__=="__main__":
    main()

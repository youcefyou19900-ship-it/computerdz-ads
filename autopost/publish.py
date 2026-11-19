#!/usr/bin/env python3
"""COMPUTER DZ autopost: publishes the approved Reels of autopost/calendar.json to the
Facebook Page and the Instagram professional account, through the official Meta Graph API.

Modes (env MODE or first argument):
  check    read-only: who the token is, Page + IG account, permissions, IG publishing quota. Publishes nothing.
  plan     read-only: lists what is due / next, without calling Meta.
  publish  publishes at most one due post (both platforms), then records it in autopost/state.json.

The token is read from the env var META_TOKEN (a GitHub Actions secret). It is never printed and never put
in a URL: every Meta request sends it in the Authorization header.
Safety switches: nothing is published unless AUTOPOST_ENABLED == "true" and the calendar entry has
"approved": true. DRY_RUN=1 runs the publish logic without any POST to Meta.
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
TZ = ZoneInfo("Africa/Algiers")
V = os.environ.get("GRAPH_VERSION", "v25.0")
GRAPH = os.environ.get("GRAPH_BASE", "https://graph.facebook.com").rstrip("/")
RUPLOAD = os.environ.get("RUPLOAD_BASE", "https://rupload.facebook.com").rstrip("/")
GH_API = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
CAL = os.environ.get("CALENDAR", os.path.join(HERE, "calendar.json"))
STATE = os.environ.get("STATE", os.path.join(HERE, "state.json"))
EARLY_MIN = int(os.environ.get("EARLY_MINUTES", "10"))      # a post may go out up to 10 min before its time
MIN_GAP_H = float(os.environ.get("MIN_GAP_HOURS", "3"))     # never two posts closer than this (catch-up runs)
MAX_LATE_H = float(os.environ.get("MAX_LATE_HOURS", "720"))  # older than this -> marked missed, not posted
QUIET = tuple(int(x) for x in os.environ.get("ACTIVE_HOURS", "9-23").split("-"))  # catch-up only 09:00–23:00
MAX_TRIES = int(os.environ.get("MAX_TRIES", "3"))
DRY = os.environ.get("DRY_RUN", "") not in ("", "0", "false")
POLL = float(os.environ.get("POLL_SECONDS", "15"))


class MetaError(Exception):
    pass


def log(*a):
    print(*a, flush=True)


def now():
    s = os.environ.get("NOW")  # tests only, "YYYY-MM-DD HH:MM" Algiers time
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=TZ) if s else dt.datetime.now(TZ)


def at(entry):
    return dt.datetime.strptime(entry["publish_at"], "%Y-%m-%d %H:%M").replace(tzinfo=TZ)


def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


# ---------------------------------------------------------------- HTTP

def _req(method, url, token=None, params=None, data=None, headers=None, timeout=300):
    h = dict(headers or {})
    if token:
        h["Authorization"] = "OAuth " + token
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    body = None
    if data is not None:
        if isinstance(data, (bytes, bytearray)):
            body = bytes(data)
        else:
            body = urllib.parse.urlencode(data).encode()
            h.setdefault("Content-Type", "application/x-www-form-urlencoded")
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            err = json.loads(raw).get("error", {})
            msg = f"{err.get('type', '')} {err.get('code', '')}/{err.get('error_subcode', '')}: {err.get('message', '')}"
        except Exception:
            msg = raw[:300].decode("utf-8", "replace")
        raise MetaError(f"HTTP {e.code} {method} {url.split('?')[0]} -> {msg}") from None
    try:
        return json.loads(raw) if raw else {}
    except ValueError:
        return {"_raw": raw[:300].decode("utf-8", "replace")}


def g_get(path, token, **params):
    return _req("GET", f"{GRAPH}/{V}/{path}", token, params=params, timeout=60)


def g_post(path, token, **data):
    if DRY:
        log(f"   [dry-run] POST /{path} {sorted(data)}")
        return {"id": "DRY", "video_id": "DRY", "success": True}
    return _req("POST", f"{GRAPH}/{V}/{path}", token, data=data, timeout=120)


def rupload(url, token, blob):
    if DRY:
        log(f"   [dry-run] upload {len(blob)} bytes")
        return {"success": True}
    return _req("POST", url, token, data=blob, timeout=900, headers={
        "offset": "0", "file_size": str(len(blob)), "Content-Type": "application/octet-stream"})


# ---------------------------------------------------------------- media

def fetch_video(name):
    """The video lives on the media branch of this repo (env MEDIA_REF, default autopost-media)."""
    local = os.environ.get("MEDIA_DIR")
    if local:
        with open(os.path.join(local, name), "rb") as f:
            return f.read()
    repo = os.environ["GITHUB_REPOSITORY"]
    ref = os.environ.get("MEDIA_REF", "autopost-media")
    url = f"{GH_API}/repos/{repo}/contents/media/{urllib.parse.quote(name)}?ref={urllib.parse.quote(ref)}"
    h = {"Accept": "application/vnd.github.raw", "X-GitHub-Api-Version": "2022-11-28"}
    if os.environ.get("GITHUB_TOKEN"):
        h["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=300) as r:
        return r.read()


# ---------------------------------------------------------------- Meta accounts

def page_token(token, page_id):
    """A System User / user token gives the Page token; a token that already is a Page token is used as is."""
    try:
        r = g_get(page_id, token, fields="access_token")
        return r.get("access_token") or token
    except MetaError:
        return token


def ids(token):
    page = os.environ.get("META_PAGE_ID", "").strip()
    ig = os.environ.get("META_IG_USER_ID", "").strip()
    if not page:  # a System User with exactly one Page assigned: use it
        acc = g_get("me/accounts", token, fields="id").get("data", [])
        if len(acc) == 1:
            page = acc[0]["id"]
    if page and not ig:
        r = g_get(page, token, fields="instagram_business_account")
        ig = (r.get("instagram_business_account") or {}).get("id", "")
    return page, ig


# ---------------------------------------------------------------- publishers

def publish_facebook(token, page_id, blob, caption):
    ptok = page_token(token, page_id)
    r = g_post(f"{page_id}/video_reels", ptok, upload_phase="start")
    vid = r.get("video_id")
    if not vid:
        raise MetaError(f"FB start: no video_id ({r})")
    up = rupload(r.get("upload_url") or f"{RUPLOAD}/video-upload/{V}/{vid}", ptok, blob)
    if not up.get("success", True):
        raise MetaError(f"FB upload failed ({up})")
    g_post(f"{page_id}/video_reels", ptok, upload_phase="finish", video_id=vid,
           video_state="PUBLISHED", description=caption)
    link = ""
    if not DRY:
        for _ in range(40):  # up to ~10 min of processing
            time.sleep(POLL)
            st = g_get(vid, ptok, fields="status,permalink_url")
            s = st.get("status") or {}
            if s.get("video_status") == "error" or (s.get("processing_phase") or {}).get("status") == "error":
                raise MetaError(f"FB processing error ({s})")
            link = st.get("permalink_url", "") or link
            if (s.get("publishing_phase") or {}).get("status") == "complete" or s.get("video_status") == "ready":
                break
    if link and link.startswith("/"):
        link = "https://www.facebook.com" + link
    return {"id": vid, "url": link}


def publish_instagram(token, ig_id, blob, caption):
    r = g_post(f"{ig_id}/media", token, media_type="REELS", upload_type="resumable",
               caption=caption, share_to_feed="true")
    cid = r.get("id")
    if not cid:
        raise MetaError(f"IG container: no id ({r})")
    up = rupload(r.get("uri") or f"{RUPLOAD}/ig-api-upload/{V}/{cid}", token, blob)
    if not up.get("success", True):
        raise MetaError(f"IG upload failed ({up})")
    if not DRY:
        for _ in range(40):  # up to ~10 min
            time.sleep(POLL)
            st = g_get(cid, token, fields="status_code,status")
            code = st.get("status_code")
            if code == "FINISHED":
                break
            if code in ("ERROR", "EXPIRED"):
                raise MetaError(f"IG container {code}: {st.get('status', '')}")
        else:
            raise MetaError("IG container not FINISHED after 10 min")
    m = g_post(f"{ig_id}/media_publish", token, creation_id=cid)
    mid = m.get("id", "")
    link = ""
    if mid and not DRY:
        try:
            link = g_get(mid, token, fields="permalink").get("permalink", "")
        except MetaError:
            pass
    return {"id": mid, "url": link}


# ---------------------------------------------------------------- calendar logic

def last_published(state):
    times = [dt.datetime.fromisoformat(p["at"]) for e in state.values() for p in e.values()
             if isinstance(p, dict) and p.get("at") and p.get("id")]
    return max(times) if times else None


def pick(cal, state, t):
    """Oldest approved, enabled entry that is due and not fully done; marks too-late ones as missed."""
    due, missed = [], []
    for e in cal["posts"]:
        if not e.get("approved") or e.get("enabled") is False:
            continue
        rec = state.get(e["id"], {})
        todo = [p for p in e.get("platforms", ["facebook", "instagram"])
                if not (rec.get(p) or {}).get("id") and (rec.get(p) or {}).get("tries", 0) < MAX_TRIES
                and not rec.get("missed")]
        if not todo or at(e) - dt.timedelta(minutes=EARLY_MIN) > t:
            continue
        started = any((rec.get(p) or {}).get("id") for p in ("facebook", "instagram"))
        if t - at(e) > dt.timedelta(hours=MAX_LATE_H) and not started:
            missed.append(e)
            continue
        due.append((at(e), e, todo))
    due.sort(key=lambda x: x[0])
    return (due[0] if due else None), missed


def run_publish():
    cal, state = load(CAL, {"posts": []}), load(STATE, {})
    t = now()
    choice, missed = pick(cal, state, t)
    for e in missed:
        state.setdefault(e["id"], {})["missed"] = t.isoformat(timespec="minutes")
        log(f"⚠️ {e['id']} ({e['publish_at']}) is more than {MAX_LATE_H:g} h late -> marked missed, not posted")
    if missed:
        save(STATE, state)
    if not choice:
        log(f"nothing due at {t:%Y-%m-%d %H:%M} (Algiers)")
        return 0
    when, e, todo = choice
    if not (QUIET[0] <= t.hour < QUIET[1]):
        log(f"{e['id']} is due, but {t:%H:%M} is outside {QUIET[0]}:00–{QUIET[1]}:00 -> waits for the morning")
        return 0
    lp = last_published(state)
    partial = any((state.get(e["id"], {}).get(p) or {}).get("id") for p in ("facebook", "instagram"))
    if lp and not partial and t - lp < dt.timedelta(hours=MIN_GAP_H):
        log(f"{e['id']} is due but the last post was at {lp:%H:%M} (< {MIN_GAP_H:g} h) -> next run")
        return 0
    if os.environ.get("AUTOPOST_ENABLED", "").lower() != "true" and not DRY:
        log(f"{e['id']} is due, but AUTOPOST_ENABLED is not 'true' -> nothing published")
        return 0
    token = os.environ.get("META_TOKEN", "")
    if not token and not DRY:
        log("META_TOKEN secret is missing")
        return 1
    log(f"▶ {e['id']} · {e['video']} · planned {e['publish_at']} · {', '.join(todo)}")
    rec = state.setdefault(e["id"], {})
    try:
        page, ig = ids(token) if token else (os.environ.get("META_PAGE_ID", "PAGE"),
                                             os.environ.get("META_IG_USER_ID", "IG"))
        blob = fetch_video(e["video"])
    except Exception as ex:  # noqa: BLE001 - counted as a try for each platform, retried next run
        log(f"  ❌ before upload: {ex}")
        if not DRY:
            for p in todo:
                slot = rec.setdefault(p, {})
                slot["tries"] = slot.get("tries", 0) + 1
                slot["error"] = str(ex)[:500]
            save(STATE, state)
        return 1
    log(f"  video {len(blob) / 1e6:.1f} MB")
    rc = 0
    for p in todo:
        slot = rec.setdefault(p, {})
        try:
            if p == "facebook":
                if not page:
                    raise MetaError("META_PAGE_ID is not set")
                res = publish_facebook(token, page, blob, e["caption"])
            elif p == "instagram":
                if not ig:
                    raise MetaError("no Instagram account linked to the Page (META_IG_USER_ID)")
                res = publish_instagram(token, ig, blob, e["caption"])
            else:
                raise MetaError(f"unknown platform {p}")
            if DRY:
                log(f"  [dry-run] {p}: ok")
                continue
            slot.update(res, at=now().isoformat(timespec="seconds"))
            slot.pop("error", None)
            log(f"  ✅ {p}: {res.get('url') or res.get('id')}")
        except Exception as ex:  # noqa: BLE001 - recorded, retried next run
            if DRY:
                log(f"  [dry-run] {p}: {ex}")
                rc = 1
                continue
            slot["tries"] = slot.get("tries", 0) + 1
            slot["error"] = str(ex)[:500]
            log(f"  ❌ {p} (try {slot['tries']}/{MAX_TRIES}): {ex}")
            rc = 1
        if not DRY:
            save(STATE, state)  # after each platform, so a crash never re-posts what already went out
    return rc


def run_check():
    token = os.environ.get("META_TOKEN", "")
    if not token:
        log("❌ META_TOKEN secret is missing")
        return 1
    rc = 0
    try:
        me = g_get("me", token, fields="id,name")
        log(f"token belongs to: {me.get('name')} ({me.get('id')})")
    except MetaError as ex:
        log(f"❌ token: {ex}")
        return 1
    try:
        perms = g_get("me/permissions", token).get("data", [])
        granted = sorted(p["permission"] for p in perms if p.get("status") == "granted")
        log("permissions: " + ", ".join(granted))
        need = {"pages_show_list", "pages_read_engagement", "pages_manage_posts", "instagram_basic",
                "instagram_content_publish"}
        miss = sorted(need - set(granted))
        if miss:
            log("⚠️ missing: " + ", ".join(miss))
            rc = 1
    except MetaError as ex:
        log(f"(permissions not readable with this token type: {ex})")
    try:
        acc = g_get("me/accounts", token, fields="id,name,instagram_business_account{id,username}").get("data", [])
        for a in acc:
            igb = a.get("instagram_business_account") or {}
            log(f"Page: {a.get('name')} · META_PAGE_ID={a.get('id')} · IG: @{igb.get('username', '—')} "
                f"META_IG_USER_ID={igb.get('id', '—')}")
        if not acc:
            log("⚠️ the token sees no Page (assign the Page to the System User)")
    except MetaError as ex:
        log(f"(me/accounts: {ex})")
    page, ig = ids(token)
    if page:
        try:
            p = g_get(page, page_token(token, page), fields="id,name,instagram_business_account{id,username}")
            log(f"✅ Page {p.get('name')} ({p.get('id')}) · IG @{(p.get('instagram_business_account') or {}).get('username', '—')}")
        except MetaError as ex:
            log(f"❌ Page {page}: {ex}")
            rc = 1
    else:
        log("⚠️ META_PAGE_ID is not set yet (repo variable)")
        rc = 1
    if ig:
        try:
            q = g_get(f"{ig}/content_publishing_limit", token, fields="config,quota_usage").get("data", [{}])[0]
            log(f"✅ IG publishing quota used: {q.get('quota_usage')} / {(q.get('config') or {}).get('quota_total')} (24 h)")
        except MetaError as ex:
            log(f"❌ IG {ig}: {ex}")
            rc = 1
    log("AUTOPOST_ENABLED = " + os.environ.get("AUTOPOST_ENABLED", "(not set)"))
    return rc


def run_plan():
    cal, state = load(CAL, {"posts": []}), load(STATE, {})
    t = now()
    log(f"now {t:%Y-%m-%d %H:%M} (Algiers) · {len(cal['posts'])} posts in calendar")
    for e in sorted(cal["posts"], key=at):
        rec = state.get(e["id"], {})
        marks = []
        for p in e.get("platforms", ["facebook", "instagram"]):
            s = rec.get(p) or {}
            marks.append({"facebook": "FB", "instagram": "IG"}.get(p, p) + ":" + ("✅" if s.get("id") else ("❌" if s.get("error") else "·")))
        flag = "missed" if rec.get("missed") else ("" if e.get("approved") else "NOT APPROVED")
        log(f"{e['publish_at']}  {e['id']:<22} {' '.join(marks)}  {flag}")
    return 0


def main():
    mode = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("MODE", "plan")).strip().lower()
    fn = {"check": run_check, "plan": run_plan, "publish": run_publish}.get(mode)
    if not fn:
        log(f"unknown mode {mode!r} (check | plan | publish)")
        return 2
    return fn()


if __name__ == "__main__":
    sys.exit(main())

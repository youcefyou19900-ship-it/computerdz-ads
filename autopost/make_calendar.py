#!/usr/bin/env python3
"""Builds autopost/calendar.json: the 30 approved COMPUTER DZ Reels (6 products × كرياتيف 1–5),
two per day at 13:00 and 20:00 (Algiers), one full round of كرياتيف 1 over the 6 products, then كرياتيف 2, … 5 (user, 19/11).
Usage: python3 make_calendar.py 2026-11-21 [--approved]"""
import datetime as dt
import json
import os
import sys

TRUST = "🛡️ ضمان 12 شهر · 👀 تتفقّدو قبل ما تخلّص · 🚚 الدفع عند الاستلام"
CTA = "📩 اطلب دركا: ابعثلنا في الميساج، نعيطولك نأكدو معاك، والخلاص كي توصلك."
TAGS = "#COMPUTERDZ #laptop #PC #2en1 #tactile #Algérie #DZ #الجزائر #لابتوب"

PRODUCTS = {
    "hp": dict(file="HP_G9", price="33000", name="HP G9 x360 — PC tactile 2-en-1",
               price_txt="💰 33 000 دج (3 مليون و 300)",
               specs=["Intel Celeron N4500", "4 GB RAM · 128 GB", "Écran tactile + stylet (Pen & touch 10 points)",
                      "x360 : PC · tablette · position pliable", "Windows 10 Pro Éducation"],
               hooks={1: ("CARDS", "PC، tablette، ولا position pliable… في جهاز واحد 👇"),
                      2: ("ETIQUETTE", "السومة قبل كلش: 33 000 دج 🏷️"),
                      3: ("SUIVI", "من الطلبية حتى الباب: تتفقّدو بيدّيك قبل ما تخلّص 📦"),
                      4: ("TABLEAU", "للأستاذة: الدرس على الشاشة، والتصحيح بالستيلو ✍️"),
                      5: ("MOSAIQUE", "جهاز واحد، بزاف وضعيات، وكل وضعية عندها خدمتها 🔄")}),
    "3310": dict(file="Dell_3310", price="40000", name="Dell Latitude 3310 — 2-en-1 tactile",
                 price_txt="💰 40 000 دج (4 مليون)",
                 specs=["Intel Core i3 (8e génération)", "4 GB RAM · 128 GB SSD NVMe",
                        "Écran tactile 360° : PC · tablette", "Windows 10 Pro Éducation"],
                 hooks={1: ("CHAT", "سقسيتونا على Dell 3310… هاو الجواب 💬"),
                        2: ("COUVERTURE", "في الغلاف هاد السمانة: Dell Latitude 3310 بـ 40 000 دج 📰"),
                        3: ("POLAROID", "التفقّد عند الباب، صورة بصورة 📸"),
                        4: ("CAHIER", "لطالب الجامعة: البحوث، المذكرة، والدروس أونلاين 📓"),
                        5: ("VERSUS", "PC ولا tablette؟ خوذ الزوج ⚔️")}),
    "3380": dict(file="Dell_3380", price="37000", name="Dell Latitude 3380 — écran tactile",
                 price_txt="💰 37 000 دج (3 مليون و 700)",
                 specs=["Intel Core i3-6006U (6e génération)", "4 GB RAM · 128 GB SSD", "Écran tactile 10 points",
                        "Windows 10 Pro"],
                 hooks={1: ("QUIZ", "Quiz: واش تعرف على Dell Latitude 3380؟ ❓"),
                        2: ("JOURNAL", "عاجل: Dell Latitude 3380 بـ 37 000 دج 🗞️"),
                        3: ("PASSEPORT", "كل خطوة بختمها: من الطلبية حتى الخلاص 🛂"),
                        4: ("TABLEUR", "للموظف في البيرو: Excel، Word، والإيمايلات 📊"),
                        5: ("CROQUIS", "écran tactile: اكتب وارسم بصبعك ✏️")}),
    "nec": dict(file="NEC_VersaPro", price="27000", name="NEC VersaPro — PC tactile 2-en-1",
                price_txt="💰 27 000 دج (2 مليون و 700)",
                specs=["Intel Celeron N4120", "4 GB RAM · 128 GB SSD", "Écran tactile 360° : PC · tablette · position pliable",
                       "Windows 10", "Batterie 4–6 h selon l'utilisation · chargeur d'origine",
                       "Clavier QWERTY japonais : l'arabe et le français marchent depuis Windows"],
                hooks={1: ("WASHI", "PC ولا tablette؟ الزوج بـ 27 000 دج 🎋"),
                       2: ("EMBARQUEMENT", "التذكرة تاعك لـ PC تاتش 2-en-1: بـ 27 000 دج ✈️"),
                       3: ("ENVELOPPE", "الطلبية توصلك للباب، وتتفقّدها قبل ما تخلّص ✉️"),
                       4: ("POSTIT", "حاسوب للدار: القراية، الخدمة، والفيلم en position pliable 🏠"),
                       5: ("KEYCAPS", "الكلافيي ياباني؟ عادي: العربية والفرنسية يخدمو من Windows ⌨️")}),
    "3120": dict(file="Dell_3120", price="35000", name="Dell Latitude 3120 — 2-en-1 tactile",
                 price_txt="💰 35 000 دج (3 مليون و 500)",
                 specs=["Intel Pentium Silver N6000", "8 GB RAM · 128 GB", "Écran tactile 10 points, 360° : PC · tablette · position pliable",
                        "Windows 10 Pro", "Batterie 4–6 h selon l'utilisation"],
                 hooks={1: ("MYTHE", "Mythe ولا réalité؟ Dell Latitude 3120 يجاوب 🤔"),
                        2: ("SCOREBOARD", "النتيجة النهائية: 35 000 دج 🏆"),
                        3: ("BD", "القصة كاملة: من الطلبية حتى الباب 💥"),
                        4: ("BIBLIOTHEQUE", "للطالب في المكتبة: الـ PDF والبحوث بصبعك 📚"),
                        5: ("JOURNEE", "Batterie 4–6 h: نهار قراية كامل ☀️")}),
    "3190": dict(file="Dell_3190", price="32000", name="Dell Latitude 3190 — 2-en-1 tactile",
                 price_txt="💰 32 000 دج (3 مليون و 200)",
                 specs=["Intel Pentium Silver N5030 (4 cœurs)", "4 GB RAM · 128 GB",
                        "Écran tactile 10 points, 360° : PC · tablette · position pliable", "Windows 10 Pro"],
                 hooks={1: ("TICKET", "الفاتورة واضحة: 32 000 دج 🧾"),
                        2: ("ARCADE", "Level up: Dell Latitude 3190 بـ 32 000 دج 🕹️"),
                        3: ("TERMINAL", "الفحص قبل الخلاص: كلش يتجرّب عند الباب 🖥️"),
                        4: ("VISIO", "تخدم من الدار؟ الاجتماعات أونلاين على شاشة تاتش 💻"),
                        5: ("SPLIT", "Avant / Après: من التيليفون للـ PC تاتش 2-en-1 ✨")}),
}
ORDER = ["hp", "3310", "3380", "nec", "3120", "3190"]  # same order as the «كرياتيف» group (user, 19/11)
SLOTS = ["13:00", "20:00"]
FORBIDDEN = ["خيمة", "tente", "TENTE", "⛺", "جديد", "مستعمل", "neuf"]


def caption(p, n):
    style, hook = p["hooks"][n]
    lines = [hook, "", "💻 " + p["name"]] + ["✅ " + s for s in p["specs"]] + ["", p["price_txt"], TRUST, CTA, "",
                                                                             "■ COMPUTER DZ", TAGS]
    txt = "\n".join(lines)
    bad = [w for w in FORBIDDEN if w in txt]
    assert not bad, (p["file"], n, bad)
    assert len(txt) < 2000
    return style, txt


def build(start, approved=False):
    d0 = dt.date.fromisoformat(start)
    posts, k = [], 0
    for n in range(1, 6):
        for key in ORDER:
            p = PRODUCTS[key]
            style, txt = caption(p, n)
            day, slot = d0 + dt.timedelta(days=k // 2), SLOTS[k % 2]
            posts.append({
                "id": f"{p['file']}_{n}_{style}",
                "video": f"{p['file']}_{n}_{style}_{p['price']}.mp4",
                "publish_at": f"{day.isoformat()} {slot}",
                "platforms": ["facebook", "instagram"],
                "approved": approved,
                "caption": txt,
            })
            k += 1
    return {"timezone": "Africa/Algiers", "note": "approved=true only after the user approved the calendar",
            "posts": posts}


if __name__ == "__main__":
    start = sys.argv[1] if len(sys.argv) > 1 else "2026-11-21"
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calendar.json")
    cal = build(start, "--approved" in sys.argv)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(cal, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"{len(cal['posts'])} posts · {cal['posts'][0]['publish_at']} → {cal['posts'][-1]['publish_at']}")

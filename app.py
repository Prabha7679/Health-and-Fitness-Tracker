"""
Fitness - Health & Fitness Tracker (Streamlit + SQLite + Plotly)
Run:  pip install streamlit pandas plotly
      streamlit run app.py
"""
import random
import sqlite3
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# set_page_config must be the first Streamlit call
st.set_page_config(page_title="VitalTrack", page_icon="🏋️", layout="wide",
                   initial_sidebar_state="collapsed")

# ============================== Global CSS ==============================
# - hides the sidebar completely (navigation now lives at the top)
# - trims the default padding so the dashboard fits on one screen
# - turns the horizontal radio into a pill-style top menu
st.markdown("""
<style>
[data-testid="stSidebar"], [data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"], footer {display:none !important;}
header[data-testid="stHeader"] {height:0; background:transparent;}
.block-container {padding:0.8rem 1.6rem 0.4rem 1.6rem !important; max-width:100% !important;}
[data-testid="stVerticalBlock"] {gap:0.55rem;}
[data-testid="stMetricValue"] {font-size:1.45rem;}
[data-testid="stMetricLabel"] p {font-size:0.8rem;}
[data-testid="stMetric"] {padding:0;}

/* top navigation pills */
div[data-testid="stRadio"] div[role="radiogroup"] {gap:6px; flex-wrap:wrap;}
.topnav div[role="radiogroup"] label[data-baseweb="radio"] {
    background:#ecfdf5; border:1px solid #bbf7d0; border-radius:999px;
    padding:6px 16px; margin:0; cursor:pointer;
}
.topnav div[role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) {
    background:linear-gradient(120deg,#0f766e,#22c55e); border-color:transparent;
}
.topnav div[role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) p {
    color:white !important; font-weight:600;
}
.topnav div[role="radiogroup"] label[data-baseweb="radio"] p {
    color:#065f46; font-size:0.95rem;
}
.brand {font-size:1.35rem; font-weight:800; color:#0f766e; white-space:nowrap; padding-top:2px;}
.streak {text-align:right; font-weight:600; padding-top:6px; white-space:nowrap;}
</style>
""", unsafe_allow_html=True)

# ============================== Constants ==============================
MET = {"Walking": 3.5, "Running": 9.8, "Cycling": 7.5, "Swimming": 6.0,
       "Yoga": 3.0, "Strength training": 5.0, "HIIT": 8.0, "Other": 4.0}
ACTIVITY = {"Sedentary": 1.2, "Light": 1.375, "Moderate": 1.55, "Active": 1.725}
DEFAULTS = {"name": "Athlete", "age": 20, "sex": "Male", "height": 170.0, "activity": "Moderate",
            "cal_goal": 2000, "ex_goal": 30, "sleep_goal": 8.0, "water_goal": 2.5}
COLS = ["calories", "burned", "duration", "sleep", "water"]
TIPS = ["💧 Stay hydrated: aim for 2-3 litres of water.",
        "🚶 Take a 10-minute walk after meals.",
        "🛌 Aim for 7-8 hours of sleep.",
        "🥦 Add more greens to your plate.",
        "🧘 Stretch for 5 minutes every morning."]

# ============================== Database ==============================
@st.cache_resource
def get_conn():
    conn = sqlite3.connect("health.db", check_same_thread=False)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS entries(
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, food TEXT,
            calories REAL DEFAULT 0, exercise TEXT, duration REAL DEFAULT 0,
            burned REAL DEFAULT 0, sleep REAL DEFAULT 0, water REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS weights(date TEXT PRIMARY KEY, kg REAL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);""")
    # one-time import from the old "tracker" table
    old = conn.execute("SELECT name FROM sqlite_master WHERE name='tracker'").fetchone()
    if old and conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0] == 0:
        conn.execute("INSERT INTO entries(date,food,calories,exercise,duration,sleep) "
                     "SELECT date,food,calories,exercise,duration,sleep FROM tracker")
    conn.commit()
    return conn


conn = get_conn()


def get_settings():
    s = dict(DEFAULTS)
    for k, v in conn.execute("SELECT key, value FROM settings"):
        if k in s:
            s[k] = type(DEFAULTS[k])(v)
    return s


def save_settings(d):
    conn.executemany("INSERT OR REPLACE INTO settings VALUES (?,?)", [(k, str(v)) for k, v in d.items()])
    conn.commit()


def load_entries():
    df = pd.read_sql("SELECT * FROM entries ORDER BY date", conn)
    df["date"] = pd.to_datetime(df["date"])
    return df


def latest_weight():
    row = conn.execute("SELECT kg FROM weights ORDER BY date DESC LIMIT 1").fetchone()
    return row[0] if row else 70.0


def seed_sample():
    foods = ["Oats & fruit", "Rice & dal", "Chicken salad", "Paneer wrap", "Pasta"]
    for i in range(14):
        d = (date.today() - timedelta(days=13 - i)).isoformat()
        ex = random.choice(["Running", "Walking", "Cycling", "Yoga", "None"])
        dur = 0 if ex == "None" else random.choice([20, 30, 45, 60])
        burned = round(MET.get(ex, 0) * latest_weight() * dur / 60)
        conn.execute("INSERT INTO entries(date,food,calories,exercise,duration,burned,sleep,water) "
                     "VALUES (?,?,?,?,?,?,?,?)",
                     (d, random.choice(foods), random.randint(1600, 2400), ex, dur, burned,
                      round(random.uniform(5.5, 8.5), 1), round(random.uniform(1.5, 3.2), 2)))
    conn.commit()


# ============================== Helpers ==============================
def show(fig):
    """Display a plotly chart on both old and new Streamlit versions."""
    try:
        st.plotly_chart(fig, width="stretch")
    except Exception:
        st.plotly_chart(fig, use_container_width=True)


def daily_frame(df, start, end):
    idx = pd.date_range(start, end)
    d = df.groupby("date")[COLS].sum().reindex(idx, fill_value=0)
    d.index.name = "date"
    return d


def avg(d, col):
    s = d[col][d[col] > 0]
    return float(s.mean()) if len(s) else 0.0


def streak(df):
    days = set(df["date"].dt.date)
    d = date.today()
    if d not in days:
        d -= timedelta(days=1)
    n = 0
    while d in days:
        n += 1
        d -= timedelta(days=1)
    return n


def bmi_info(w, h_cm):
    bmi = w / ((h_cm / 100) ** 2)
    cat = "Underweight" if bmi < 18.5 else "Healthy" if bmi < 25 else "Overweight" if bmi < 30 else "Obese"
    return bmi, cat


def bmr_tdee(S, w):
    bmr = 10 * w + 6.25 * S["height"] - 5 * S["age"] + (5 if S["sex"] == "Male" else -161)
    return bmr, bmr * ACTIVITY[S["activity"]]


def gauge(title, value, goal, unit, color, height=150):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value, number={"suffix": unit, "font": {"size": 22}},
        title={"text": title, "font": {"size": 13}},
        gauge={"axis": {"range": [0, max(goal * 1.5, value * 1.1)]}, "bar": {"color": color},
               "threshold": {"line": {"color": "red", "width": 3}, "value": goal}}))
    fig.update_layout(height=height, margin=dict(t=38, b=8, l=22, r=22))
    return fig


def goal_chart(fig, goal, height=340):
    fig.add_hline(y=goal, line_dash="dash", line_color="red", annotation_text="Goal")
    fig.update_layout(height=height, margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h"))
    show(fig)


def banner(title, subtitle):
    st.markdown(f"""<div style="padding:12px 20px;border-radius:12px;margin-bottom:6px;
        background:linear-gradient(120deg,#0f766e,#22c55e);color:white">
        <div style="font-size:24px;font-weight:700">{title}</div>
        <div style="opacity:.9;font-size:14px">{subtitle}</div></div>""", unsafe_allow_html=True)


# ============================== Pages ==============================
def page_dashboard(S):
    df = load_entries()

    # ---- slim header: greeting on the left, period picker on the right ----
    h1, h2 = st.columns([3, 2])
    h1.markdown(f"### 👋 Welcome back, {S['name']}  \n"
                f"<span style='opacity:.7;font-size:14px'>Your personal dashboard for health goals</span>",
                unsafe_allow_html=True)

    if df.empty:
        st.info("No entries yet. Add your first one in **Daily Tracker**, or try some sample data.")
        if st.button("Load sample data"):
            seed_sample()
            st.rerun()
        return

    period = h2.radio("Period", ["Last 7 days", "Last 30 days", "All time"], horizontal=True,
                      key="period", label_visibility="collapsed")
    today = pd.Timestamp(date.today())
    prev = None
    if period == "All time":
        start = min(df["date"].min(), today)
    else:
        n = 7 if "7" in period else 30
        start = today - pd.Timedelta(days=n - 1)
        prev = daily_frame(df, start - pd.Timedelta(days=n), start - pd.Timedelta(days=1))
    d = daily_frame(df, start, today)

    def delta(col, fmt):
        if prev is None or avg(prev, col) == 0:
            return None
        return fmt.format(avg(d, col) - avg(prev, col))

    # ---- KPI row ----
    k = st.columns(5)
    k[0].metric("Avg intake", f"{avg(d, 'calories'):.0f} kcal", delta("calories", "{:+.0f}"))
    k[1].metric("Calories burned", f"{d['burned'].sum():.0f} kcal")
    k[2].metric("Active minutes", f"{d['duration'].sum():.0f} min")
    k[3].metric("Avg sleep", f"{avg(d, 'sleep'):.1f} h", delta("sleep", "{:+.1f}"))
    k[4].metric("Avg water", f"{avg(d, 'water'):.1f} L", delta("water", "{:+.1f}"))

    # ---- middle row: today's goals (left, 2x2) + trends (right) ----
    left, right = st.columns([5, 7])
    t = d.loc[today]
    with left:
        st.markdown("**🎯 Today's goals**")
        r1 = st.columns(2)
        with r1[0]: show(gauge("Calories eaten", t["calories"], S["cal_goal"], " kcal", "#f97316"))
        with r1[1]: show(gauge("Exercise", t["duration"], S["ex_goal"], " min", "#0d9488"))
        r2 = st.columns(2)
        with r2[0]: show(gauge("Sleep", t["sleep"], S["sleep_goal"], " h", "#8b5cf6"))
        with r2[1]: show(gauge("Water", t["water"], S["water_goal"], " L", "#3b82f6"))

    CH = 285  # chart height inside the tabs (matches the gauge block on the left)
    with right:
        tabs = st.tabs(["📈 Nutrition", "Activity", "Sleep", "Hydration"])
        with tabs[0]:
            fig = go.Figure()
            fig.add_bar(x=d.index, y=d["calories"], name="Eaten", marker_color="#f97316")
            fig.add_bar(x=d.index, y=d["burned"], name="Burned", marker_color="#0d9488")
            fig.update_layout(barmode="group")
            goal_chart(fig, S["cal_goal"], CH)
        with tabs[1]:
            c1, c2 = st.columns([2, 1])
            with c1:
                goal_chart(px.bar(d.reset_index(), x="date", y="duration", labels={"duration": "Minutes"},
                                  color_discrete_sequence=["#0d9488"]), S["ex_goal"], CH)
            sub = df[(df["date"] >= start) & (df["exercise"].fillna("None") != "None") & (df["duration"] > 0)]
            with c2:
                if sub.empty:
                    st.info("No workouts in this period.")
                else:
                    pie = px.pie(sub.groupby("exercise", as_index=False)["duration"].sum(),
                                 names="exercise", values="duration", hole=0.45)
                    pie.update_layout(height=CH, margin=dict(t=10, b=10, l=0, r=0),
                                      legend=dict(orientation="h", y=-0.1))
                    show(pie)
        with tabs[2]:
            goal_chart(px.line(d.reset_index(), x="date", y="sleep", markers=True, labels={"sleep": "Hours"},
                               color_discrete_sequence=["#8b5cf6"]), S["sleep_goal"], CH)
        with tabs[3]:
            goal_chart(px.bar(d.reset_index(), x="date", y="water", labels={"water": "Litres"},
                              color_discrete_sequence=["#3b82f6"]), S["water_goal"], CH)

    # ---- bottom row: compact achievements + tip ----
    w = daily_frame(df, today - pd.Timedelta(days=6), today)
    st_ = streak(df)
    badges = [("🥇 Consistency Star", min(st_, 7), 7),
              ("💪 Workout Warrior", min(int((w["duration"] >= S["ex_goal"]).sum()), 5), 5),
              ("😴 Sleep Champion", min(int((w["sleep"] >= S["sleep_goal"]).sum()), 5), 5),
              ("💧 Hydration Hero", min(int((w["water"] >= S["water_goal"]).sum()), 5), 5)]
    for col, (name, got, need) in zip(st.columns(4), badges):
        with col, st.container(border=True):
            label = f"{name} · {got}/{need}" + ("  ✅" if got >= need else "")
            st.progress(got / need, text=label)
    st.caption(f"🔥 Current streak: **{st_} day(s)**   |   🌟 Tip of the day: "
               f"{random.Random(date.today().toordinal()).choice(TIPS)}")


def page_tracker(S):
    banner("Daily Tracker", "Log meals, workouts, sleep and water")
    weight = latest_weight()
    with st.form("log", clear_on_submit=True):
        c1, c2 = st.columns(2)
        d = c1.date_input("Date", date.today(), max_value=date.today())
        food = c1.text_input("Meal / food")
        cal = c1.number_input("Calories eaten (kcal)", 0, 10000, 0, step=50)
        ex = c2.selectbox("Exercise", ["None"] + list(MET))
        dur = c2.number_input("Duration (minutes)", 0, 600, 0, step=5)
        sleep = c2.number_input("Sleep (hours)", 0.0, 24.0, 0.0, step=0.5)
        water = c2.number_input("Water (litres)", 0.0, 10.0, 0.0, step=0.25)
        ok = st.form_submit_button("Save entry")
    if ok:
        if ex == "None" and dur > 0:
            st.warning("Pick an exercise type for the duration you entered.")
        elif not (food or cal or dur or sleep or water):
            st.warning("Enter at least one value before saving.")
        else:
            burned = round(MET.get(ex, 0) * weight * dur / 60)
            conn.execute("INSERT INTO entries(date,food,calories,exercise,duration,burned,sleep,water) "
                         "VALUES (?,?,?,?,?,?,?,?)", (d.isoformat(), food, cal, ex, dur, burned, sleep, water))
            conn.commit()
            st.success(f"Entry saved. Estimated burn: {burned} kcal (using {weight:.1f} kg).")

    st.markdown("### 🗂️ Your entries")
    df = load_entries()
    if df.empty:
        st.info("Nothing logged yet.")
        return
    view = df.sort_values(["date", "id"], ascending=False).copy()
    view["date"] = view["date"].dt.date
    view.insert(0, "Delete", False)
    cols = list(view.columns)
    edited = st.data_editor(view, hide_index=True, key="editor", disabled=[c for c in cols if c != "Delete"])
    b1, b2 = st.columns([1, 5])
    if b1.button("Delete selected"):
        ids = edited.loc[edited["Delete"], "id"].tolist()
        if ids:
            conn.executemany("DELETE FROM entries WHERE id=?", [(int(i),) for i in ids])
            conn.commit()
            st.rerun()
        else:
            st.warning("Tick the rows you want to delete first.")
    b2.download_button("Download CSV", df.to_csv(index=False).encode(), "health_entries.csv", "text/csv")


def page_body(S):
    banner("Body & BMI", "Track your weight and daily calorie needs")
    with st.form("wf", clear_on_submit=True):
        c1, c2 = st.columns(2)
        wd = c1.date_input("Date", date.today(), max_value=date.today())
        kg = c2.number_input("Weight (kg)", 20.0, 300.0, float(round(latest_weight(), 1)), step=0.1)
        if st.form_submit_button("Save weight"):
            conn.execute("INSERT OR REPLACE INTO weights VALUES (?,?)", (wd.isoformat(), kg))
            conn.commit()
            st.success("Weight saved.")
    w = latest_weight()
    bmi, cat = bmi_info(w, S["height"])
    bmr, tdee = bmr_tdee(S, w)
    h = S["height"] / 100
    m = st.columns(4)
    m[0].metric("Weight", f"{w:.1f} kg")
    m[1].metric("BMI", f"{bmi:.1f}", cat, delta_color="off")
    m[2].metric("BMR", f"{bmr:.0f} kcal")
    m[3].metric("Daily needs (TDEE)", f"{tdee:.0f} kcal")
    st.caption(f"Healthy weight range for {S['height']:.0f} cm: {18.5 * h * h:.1f} to {24.9 * h * h:.1f} kg. "
               "Update height, age and activity in Settings.")
    wdf = pd.read_sql("SELECT * FROM weights ORDER BY date", conn)
    if len(wdf) > 1:
        fig = px.line(wdf, x="date", y="kg", markers=True, title="Weight trend")
        fig.update_layout(height=320)
        show(fig)
    st.markdown("### Calorie targets")
    st.table(pd.DataFrame({"Goal": ["Lose weight", "Maintain", "Gain muscle"],
                           "Calories per day": [round(tdee - 500), round(tdee), round(tdee + 300)]}))


MEALS = {
    "Lose Weight": {"Veg": ["🥗 Grilled paneer salad", "🥣 Oats with fruits", "🥦 Steamed vegetables",
                            "🍲 Lentil soup with spinach", "🥪 Whole grain vegetable sandwich"],
                    "Non-Veg": ["🥗 Grilled chicken salad", "🥣 Oats with boiled eggs", "🥦 Steamed fish with veggies",
                                "🍲 Chicken and vegetable soup", "🥪 Whole grain chicken sandwich"]},
    "Gain Muscle": {"Veg": ["🥤 Protein shake with soy milk", "🍛 Brown rice with paneer curry",
                            "🍳 Lentils and avocado toast", "🥗 Chickpea salad with olive oil",
                            "🥪 Peanut butter whole grain sandwich"],
                    "Non-Veg": ["🥤 Protein shake with banana", "🍗 Brown rice with chicken", "🍳 Eggs and avocado toast",
                                "🥗 Tuna salad with olive oil", "🥪 Turkey breast whole grain sandwich"]},
    "Maintain Fitness": {"Veg": ["🍛 Balanced plate with rice, dal, veggies", "🥤 Smoothie with nuts",
                                 "🥪 Whole grain vegetable sandwich", "🥗 Sprouts salad with lemon",
                                 "🍲 Vegetable soup with quinoa"],
                         "Non-Veg": ["🍛 Balanced plate with rice, fish curry, veggies", "🥤 Smoothie with yogurt and nuts",
                                     "🥪 Whole grain chicken sandwich", "🥗 Egg salad with greens",
                                     "🍲 Chicken broth with vegetables"]},
}
SLOTS = ["Breakfast", "Mid-morning", "Lunch", "Evening snack", "Dinner"]


def page_meals(S):
    banner("Meal Planner", "Pick a goal and food preference")
    c1, c2 = st.columns(2)
    goal = c1.selectbox("Your goal", list(MEALS))
    pref = c2.radio("Preference", ["Veg", "Non-Veg"], horizontal=True)
    _, tdee = bmr_tdee(S, latest_weight())
    target = tdee - 500 if goal == "Lose Weight" else tdee + 300 if goal == "Gain Muscle" else tdee
    st.info(f"Suggested daily target for this goal: **{target:.0f} kcal**")
    for slot, meal in zip(SLOTS, MEALS[goal][pref]):
        with st.container(border=True):
            st.markdown(f"**{slot}**: {meal}")


WORKOUTS = {
    "Beginner": ["🏋️ Bodyweight Squats – 3 x 12", "🤸 Knee Push-Ups – 3 x 8-10", "🦵 Lunges – 3 x 10 each leg",
                 "🧘 Plank – hold 20-30 s", "🍑 Glute Bridges – 3 x 12", "🏃 Mountain Climbers – 3 x 20 s",
                 "🚴 Bicycle Crunches – 3 x 12", "🪑 Wall Sit – hold 20-30 s", "⬆️ Step-Ups – 3 x 10 each leg",
                 "💪 Chair Tricep Dips – 3 x 8-10"],
    "Intermediate": ["🏋️ Goblet Squats – 3 x 12", "🤸 Push-Ups – 3 x 12", "💪 Dumbbell Rows – 3 x 10",
                     "🧘 Plank Shoulder Taps – 3 x 12", "🔄 Russian Twists – 3 x 20", "🔥 Burpees – 3 x 10",
                     "🦵 Lateral Lunges – 3 x 10 each side", "🐞 Dead Bugs – 3 x 12", "⭐ Jumping Jacks – 3 x 30 s",
                     "🏋️ Dumbbell Deadlifts – 3 x 10"],
    "Advanced": ["🏋️ Barbell Squat – 4 x 8", "🏋️ Deadlift – 4 x 6-8", "💪 Pull-Ups – 4 x 8-10",
                 "🏋️ Barbell Bench Press – 4 x 8", "🏋️ Kettlebell Swing – 4 x 15",
                 "🦵 Bulgarian Split Squat – 3 x 10 each leg", "🏋️ Overhead Press – 4 x 8",
                 "🔥 Thrusters – 3 x 12", "⬆️ Box Jumps – 3 x 12", "🔥 Battle Ropes – 3 x 30 s"],
}


def page_workouts(S):
    banner("Workout Planner", "Tick off exercises as you complete them")
    level = st.selectbox("Your level", list(WORKOUTS))
    items = WORKOUTS[level]
    done = sum(st.checkbox(w, key=f"w_{level}_{i}") for i, w in enumerate(items))
    st.progress(done / len(items), text=f"{done}/{len(items)} completed")
    if done == len(items):
        st.balloons()
        st.success("Workout complete! Log it in Daily Tracker.")


def page_settings(S):
    banner("Settings", "Profile and daily goals are saved between sessions")
    with st.form("settings"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name", S["name"])
        age = c1.number_input("Age", 10, 100, int(S["age"]))
        sex = c1.selectbox("Sex", ["Male", "Female"], index=["Male", "Female"].index(S["sex"]))
        height = c1.number_input("Height (cm)", 100.0, 250.0, float(S["height"]))
        act = c1.selectbox("Activity level", list(ACTIVITY), index=list(ACTIVITY).index(S["activity"]))
        cal = c2.number_input("Daily calorie goal (kcal)", 800, 6000, int(S["cal_goal"]), step=50)
        ex = c2.number_input("Daily exercise goal (min)", 5, 300, int(S["ex_goal"]), step=5)
        sl = c2.number_input("Daily sleep goal (hours)", 4.0, 12.0, float(S["sleep_goal"]), step=0.5)
        wa = c2.number_input("Daily water goal (litres)", 0.5, 8.0, float(S["water_goal"]), step=0.25)
        if st.form_submit_button("Save settings"):
            save_settings({"name": name.strip() or "Athlete", "age": age, "sex": sex, "height": height,
                           "activity": act, "cal_goal": cal, "ex_goal": ex, "sleep_goal": sl, "water_goal": wa})
            st.success("Saved.")
            st.rerun()
    with st.expander("Data tools"):
        if st.button("Load 14 days of sample data"):
            seed_sample()
            st.success("Sample data added.")
        if st.checkbox("I understand this deletes all my entries") and st.button("Delete all entries"):
            conn.execute("DELETE FROM entries")
            conn.execute("DELETE FROM weights")
            conn.commit()
            st.success("All data deleted.")


# ============================== Router (top navigation) ==============================
PAGES = {"📊 Dashboard": page_dashboard, "✍️ Daily Tracker": page_tracker, "⚖️ Body & BMI": page_body,
         "🍎 Meal Planner": page_meals, "💪 Workout Planner": page_workouts, "⚙️ Settings": page_settings}

settings = get_settings()

nav_brand, nav_menu, nav_streak = st.columns([1.3, 7, 1.7])
nav_brand.markdown("<div class='brand'>🏋️ VitalTrack</div>", unsafe_allow_html=True)
with nav_menu:
    st.markdown("<div class='topnav'>", unsafe_allow_html=True)
    page = st.radio("Navigation", list(PAGES), horizontal=True, label_visibility="collapsed", key="nav")
    st.markdown("</div>", unsafe_allow_html=True)
streak_slot = nav_streak.empty()  # filled after the page runs so the streak is always up to date

PAGES[page](settings)

streak_slot.markdown(f"<div class='streak'>🔥 {streak(load_entries())} day streak</div>",
                     unsafe_allow_html=True)
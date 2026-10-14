"""Plotly figure builders (consistent style)."""
import plotly.graph_objects as go

from .data import FEATURES, PLAN_ORDER, SIZE_ORDER

BLUE, LIGHT, ORANGE, GRAY, GREEN = "#2563EB", "#93C5FD", "#F97316", "#94A3B8", "#10B981"
PLAN_COLORS = {"Starter": "#F59E0B", "Professional": "#60A5FA", "Enterprise": "#1D4ED8"}
COHORT_COLORS = {"New (signed up in window)": ORANGE, "Established (signed up before window)": BLUE}
FONT = dict(family='-apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", sans-serif', size=12, color="#334155")


def style(fig, height=340, legend=True, title=None, ytitle=None, xtitle=None, ypct=False):
    fig.update_layout(
        template="plotly_white", height=height, font=FONT, margin=dict(l=10, r=10, t=40 if title else 10, b=10),
        title=dict(text=title, x=0, font=dict(size=14, color="#0F172A")) if title else None,
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF", hoverlabel=dict(font_size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, title=None) if legend else None,
        showlegend=legend)
    fig.update_xaxes(title=xtitle, showgrid=False, linecolor="#CBD5E1")
    fig.update_yaxes(title=ytitle, gridcolor="#E2E8F0", zeroline=False,
                     ticksuffix="%" if ypct else None)
    return fig


def _order(df, col, order):
    present = [o for o in order if o in set(df[col])]
    return df.set_index(col).loc[present].reset_index()


def dau_trend(d):
    fig = go.Figure()
    fig.add_bar(x=d.date, y=d.dau, name="DAU", marker_color="#DBEAFE",
                hovertemplate="%{x|%a %b %d}<br>DAU: %{y:,}<extra></extra>")
    fig.add_scatter(x=d.date, y=d.dau_7d_avg, name="7-day average", mode="lines", line=dict(color=BLUE, width=3),
                    hovertemplate="%{x|%b %d}<br>7-day avg: %{y:.1f}<extra></extra>")
    return style(fig, 340, ytitle="Daily active users")


def mau_bars(m):
    labels = [f"{r.month}{' (partial)' if r.partial else ''}" for r in m.itertuples()]
    fig = go.Figure(go.Bar(x=labels, y=m.mau, marker_color=[LIGHT if p else BLUE for p in m.partial],
                           text=[f"{v:,}" for v in m.mau], textposition="outside",
                           customdata=m[["avg_dau", "dau_mau_ratio"]].values,
                           hovertemplate="%{x}<br>MAU: %{y:,}<br>Avg DAU: %{customdata[0]:.1f}"
                                         "<br>DAU/MAU: %{customdata[1]:.3f}<extra></extra>"))
    fig = style(fig, 340, legend=False, ytitle="Monthly active users")
    fig.update_yaxes(range=[0, max(m.mau.max() * 1.15, 1)])
    return fig


def activation_by_plan(a):
    a = _order(a, "segment", PLAN_ORDER)
    fig = go.Figure(go.Bar(
        x=a.segment, y=a.activation_rate_pct, marker_color=[PLAN_COLORS[p] for p in a.segment],
        text=[f"{r.activation_rate_pct:.1f}%<br>{r.activated_accounts}/{r.cohort_accounts}" for r in a.itertuples()],
        textposition="outside", hovertemplate="%{x}<br>Activation: %{y:.1f}%<extra></extra>"))
    fig = style(fig, 340, legend=False, ytitle="Activation rate", ypct=True)
    fig.update_yaxes(range=[0, max(a.activation_rate_pct.max() * 1.3, 10)])
    return fig


def user_engagement(u):
    u = _order(u, "segment", PLAN_ORDER)
    fig = go.Figure()
    fig.add_bar(x=u.segment, y=u.active_users, name="Active users", marker_color=BLUE,
                text=[f"{r.pct_users_active:.1f}%" for r in u.itertuples()], textposition="inside",
                textfont=dict(color="white"))
    fig.add_bar(x=u.segment, y=u.not_active_users, name="Not active in range", marker_color="#E2E8F0")
    fig.update_layout(barmode="stack")
    return style(fig, 340, ytitle="Users")


def feature_adoption_bar(f):
    f = f.iloc[::-1]
    fig = go.Figure()
    fig.add_bar(y=f.feature_name, x=f.user_adoption_pct, name="% of active users", orientation="h", marker_color=LIGHT,
                text=[f"{v:.1f}%" for v in f.user_adoption_pct], textposition="outside")
    fig.add_bar(y=f.feature_name, x=f.account_adoption_pct, name="% of active accounts", orientation="h", marker_color=BLUE,
                text=[f"{v:.1f}%" for v in f.account_adoption_pct], textposition="outside")
    fig = style(fig, 360, xtitle="Adoption rate")
    fig.update_xaxes(range=[0, 110], ticksuffix="%")
    fig.update_layout(barmode="group")
    return fig


def new_vs_est(nv):
    fig = go.Figure()
    for cohort in ["Established (signed up before window)", "New (signed up in window)"]:
        d = nv[nv.cohort == cohort].set_index("feature_name").reindex(FEATURES)
        if d.adoption_pct.isna().all():
            continue
        fig.add_bar(x=FEATURES, y=d.adoption_pct, name=cohort, marker_color=COHORT_COLORS[cohort],
                    text=[f"{v:.1f}%" for v in d.adoption_pct], textposition="outside",
                    customdata=d[["adopting_accounts", "active_accounts"]].values,
                    hovertemplate="%{x}<br>%{y:.1f}% (%{customdata[0]} of %{customdata[1]} accounts)<extra></extra>")
    fig = style(fig, 360, ytitle="% of active accounts", ypct=True)
    fig.update_yaxes(range=[0, 110])
    fig.update_layout(barmode="group")
    return fig


def adoption_by_plan(g):
    fig = go.Figure()
    for plan in PLAN_ORDER:
        d = g[g.subscription_plan == plan].set_index("feature_name").reindex(FEATURES)
        if d.adoption_pct.isna().all():
            continue
        fig.add_bar(x=FEATURES, y=d.adoption_pct.fillna(0), name=plan, marker_color=PLAN_COLORS[plan],
                    hovertemplate="%{x}<br>" + plan + ": %{y:.1f}% of active accounts<extra></extra>")
    fig = style(fig, 360, ytitle="% of active accounts in plan", ypct=True)
    fig.update_layout(barmode="group")
    return fig


def event_mix_by_plan(g):
    fig = go.Figure()
    palette = ["#1D4ED8", "#60A5FA", "#93C5FD", "#F59E0B", "#10B981", "#F97316"]
    plans = [p for p in PLAN_ORDER if p in set(g.subscription_plan)]
    for feat, col in zip(FEATURES, palette):
        d = g[g.feature_name == feat].set_index("subscription_plan").reindex(plans)
        fig.add_bar(x=plans, y=d.pct_of_plan_events.fillna(0), name=feat, marker_color=col,
                    hovertemplate="%{x}<br>" + feat + ": %{y:.1f}% of plan events<extra></extra>")
    fig = style(fig, 360, ytitle="% of plan's events", ypct=True)
    fig.update_layout(barmode="stack")
    return fig


def usage_frequency(f):
    f = f.sort_values("events")
    fig = go.Figure(go.Bar(y=f.feature_name, x=f.events, orientation="h", marker_color=BLUE,
                           text=[f"{p:.1f}%" for p in f.pct_of_all_events], textposition="outside",
                           customdata=f[["events_per_using_user"]].values,
                           hovertemplate="%{y}<br>Events: %{x:,}<br>Events per using user: %{customdata[0]:.1f}<extra></extra>"))
    fig = style(fig, 340, legend=False, xtitle="Events (label = share of all events)")
    fig.update_xaxes(range=[0, max(f.events.max() * 1.18, 1)])
    return fig


def inactivity_stack(s, order, xtitle):
    s = _order(s, "segment", order)
    fig = go.Figure()
    fig.add_bar(x=s.segment, y=s.lapsed_pct, name="Lapsed (active earlier, silent last 30 days)", marker_color=ORANGE)
    fig.add_bar(x=s.segment, y=s.never_pct, name="Never active in window", marker_color="#9A3412")
    fig.add_scatter(x=s.segment, y=s.inactive_pct, mode="text", showlegend=False,
                    text=[f"{r.inactive_pct:.1f}%<br>{r.inactive_accounts}/{r.eligible_accounts}" for r in s.itertuples()],
                    textposition="top center", hoverinfo="skip")
    fig = style(fig, 340, ytitle="% of eligible accounts", xtitle=xtitle, ypct=True)
    fig.update_layout(barmode="stack")
    fig.update_yaxes(range=[0, max(s.inactive_pct.max() * 1.3, 10)])
    return fig


def segment_bar(g, metric, label, order=None, pct_axis=False):
    g = _order(g, "segment", order) if order else g.sort_values(metric)
    colors = [PLAN_COLORS.get(x, BLUE) for x in g.segment]
    fig = go.Figure(go.Bar(x=g[metric], y=g.segment, orientation="h", marker_color=colors,
                           text=[f"{v:.1f}%" if pct_axis else f"{v:.1f}" for v in g[metric]], textposition="outside",
                           customdata=g[["accounts", "active_accounts"]].values,
                           hovertemplate="%{y}<br>" + label + ": %{x:.1f}<br>Accounts: %{customdata[0]} "
                                         "(active %{customdata[1]})<extra></extra>"))
    fig = style(fig, max(260, 52 * len(g) + 60), legend=False, xtitle=label)
    fig.update_xaxes(range=[0, max(g[metric].max() * 1.18, 1)])
    if order:
        fig.update_yaxes(autorange="reversed")
    return fig


def engagement_trend(d):
    fig = go.Figure()
    fig.add_scatter(x=d.date, y=d.events_7d_avg, name="Events per day (7-day avg)", line=dict(color=BLUE, width=3),
                    hovertemplate="%{x|%b %d}<br>Events: %{y:.0f}<extra></extra>")
    fig.add_scatter(x=d.date, y=d.active_accounts_7d_avg, name="Active accounts per day (7-day avg)", yaxis="y2",
                    line=dict(color=ORANGE, width=3), hovertemplate="%{x|%b %d}<br>Active accounts: %{y:.0f}<extra></extra>")
    fig = style(fig, 340, ytitle="Events per day")
    fig.update_layout(yaxis2=dict(title="Active accounts per day", overlaying="y", side="right", showgrid=False))
    return fig

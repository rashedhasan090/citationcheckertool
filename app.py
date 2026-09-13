import json
import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from citeguard.auth import (
    PLANS, admin_stats, authenticate, consume_credits, create_reset_token, create_user,
    get_user, init_db, list_users, recent_runs, record_run, refund_credits,
    reset_password, tier_allows,
)
from citeguard.billing import billing_configured, payment_link
from citeguard.engine import VerificationEngine
from citeguard.exporters import export_pdf, flatten
from citeguard.parsers import extract_references_section, extract_text_from_file, parse_citations

APP_VERSION = "3.0.0"
st.set_page_config(page_title="CiteGuard — Research Integrity", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.stApp {background:radial-gradient(circle at 5% 0%,rgba(37,99,235,.10),transparent 28%),radial-gradient(circle at 95% 3%,rgba(124,58,237,.11),transparent 27%),#f8fafc}
.block-container {max-width:1240px;padding-top:1.5rem;padding-bottom:4rem}
.cg-hero {padding:2.7rem 3rem;border-radius:28px;color:white;background:linear-gradient(120deg,#0f172a 0%,#1e3a8a 48%,#6d28d9 100%);box-shadow:0 24px 70px rgba(30,58,138,.20);margin-bottom:1.4rem}
.cg-hero h1 {font-size:3rem;line-height:1.04;margin:.55rem 0 .8rem;letter-spacing:-.04em}.cg-hero p{font-size:1.1rem;max-width:800px;color:#dbeafe}
.cg-pill{display:inline-block;border:1px solid rgba(255,255,255,.25);background:rgba(255,255,255,.10);padding:.32rem .68rem;border-radius:999px;margin-right:.35rem;font-size:.8rem}
.cg-card,.cg-plan{background:rgba(255,255,255,.94);border:1px solid #e2e8f0;border-radius:20px;padding:1.25rem;box-shadow:0 10px 30px rgba(15,23,42,.06);height:100%}.cg-plan{min-height:300px}.cg-featured{border:2px solid #4f46e5;box-shadow:0 14px 40px rgba(79,70,229,.14)}
.cg-price{font-size:2rem;font-weight:800;color:#0f172a}.cg-muted{color:#64748b}.cg-lock{border:1px dashed #cbd5e1;border-radius:16px;padding:1rem;background:#f8fafc}
.cg-low{color:#047857;font-weight:800}.cg-moderate{color:#b45309;font-weight:800}.cg-high,.cg-critical{color:#b91c1c;font-weight:800}
[data-testid="stMetric"]{background:white;border:1px solid #e2e8f0;padding:12px 14px;border-radius:16px;box-shadow:0 6px 20px rgba(15,23,42,.04)}
[data-testid="stSidebar"]{border-right:1px solid #e2e8f0}div.stButton>button{border-radius:12px;font-weight:650}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def bootstrap():
    init_db()
    return True


try:
    bootstrap()
except Exception as exc:
    st.error(f"Database initialization failed: {exc}")
    st.stop()


def hero():
    st.markdown(f"""
<div class="cg-hero"><span class="cg-pill">CiteGuard v{APP_VERSION}</span><span class="cg-pill">Evidence-first</span><span class="cg-pill">Research integrity</span>
<h1>Verify citations before they become credibility problems.</h1>
<p>Cross-check scholarly references across independent indexes, detect metadata inconsistencies and post-publication integrity signals, and preserve an auditable evidence trail for every citation.</p></div>
""", unsafe_allow_html=True)


def plan_cards(current=None, interactive=False):
    cols = st.columns(4)
    for col, tier in zip(cols, ["free", "researcher", "pro", "lab"]):
        p = PLANS[tier]
        featured = " cg-featured" if tier == "pro" else ""
        features = "".join(f"<li>{x}</li>" for x in p["features"])
        badge = " · Current" if current == tier else ""
        col.markdown(f'<div class="cg-plan{featured}"><h3>{p["name"]}{badge}</h3><div class="cg-price">{p["price"]}</div><p class="cg-muted">{p["credits"]} credits</p><ul>{features}</ul></div>', unsafe_allow_html=True)
        if interactive and tier != "free" and current != tier:
            link = payment_link(tier)
            if link:
                col.link_button(f"Upgrade to {p['name']}", link, use_container_width=True)
            else:
                col.button(f"{p['name']} billing soon", disabled=True, use_container_width=True, key=f"pay_{tier}")


def reset_screen(token):
    hero(); st.subheader("Set your CiteGuard password")
    with st.form("reset_form"):
        p1 = st.text_input("New password", type="password")
        p2 = st.text_input("Confirm password", type="password")
        go = st.form_submit_button("Set password", type="primary")
    if go:
        if p1 != p2:
            st.error("Passwords do not match.")
        else:
            try:
                ok = reset_password(str(token), p1)
            except ValueError as exc:
                st.error(str(exc)); return
            if ok:
                st.success("Password set successfully. Remove the reset parameter from the URL and sign in.")
                st.query_params.clear()
            else:
                st.error("This reset link is invalid or expired.")


def public_site():
    hero()
    cols = st.columns(4)
    features = [
        ("🔎", "Multi-source verification", "Crossref, OpenAlex, Semantic Scholar, PubMed, arXiv and Open Library."),
        ("🧬", "Citation fingerprint", "Detect DOI/title/author disagreement and possible composite references."),
        ("⚠️", "Integrity intelligence", "Separate retractions and corrections from simple existence checks."),
        ("📚", "Evidence discovery", "Find real scholarly records and inspect impact, open-access and provenance signals."),
    ]
    for col, (icon, title, text) in zip(cols, features):
        col.markdown(f'<div class="cg-card"><h3>{icon} {title}</h3><p class="cg-muted">{text}</p></div>', unsafe_allow_html=True)
    st.markdown("### Plans for researchers and research teams")
    plan_cards()
    st.divider()
    left, right = st.columns([1.1, 1])
    with left:
        st.markdown("### More than an existence checker")
        st.markdown("""
- **Metadata integrity:** detect real identifiers attached to the wrong title, authors, year, or venue.
- **Independent corroboration:** show which scholarly indexes support the strongest match.
- **Post-publication intelligence:** surface retraction and correction metadata when available.
- **Explicit uncertainty:** unresolved does not automatically mean fabricated.
- **Human-review workflow:** integrity scores are triage signals, never misconduct verdicts.
""")
    with right:
        login_tab, signup_tab = st.tabs(["Sign in", "Create free account"])
        with login_tab:
            with st.form("login"):
                login = st.text_input("Username or email")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Sign in", type="primary", use_container_width=True)
            if submit:
                user = authenticate(login, password)
                if user:
                    st.session_state["user_id"] = user.id; st.rerun()
                st.error("Invalid username/email or password.")
            with st.expander("Forgot password?"):
                email = st.text_input("Account email", key="forgot_email")
                if st.button("Request reset"):
                    create_reset_token(email) if email else None
                    st.info("If the account exists, a reset request has been recorded. Automated transactional delivery will be enabled with the production auth backend.")
        with signup_tab:
            with st.form("signup"):
                username = st.text_input("Username")
                email = st.text_input("Email")
                p1 = st.text_input("Password", type="password")
                p2 = st.text_input("Confirm password", type="password")
                agreed = st.checkbox("I will treat CiteGuard results as audit evidence requiring human review.")
                submit = st.form_submit_button("Create account — 100 free credits", type="primary", use_container_width=True)
            if submit:
                if p1 != p2: st.error("Passwords do not match.")
                elif not agreed: st.error("Please accept the responsible-use statement.")
                else:
                    try:
                        user = create_user(username, email, p1)
                        st.session_state["user_id"] = user.id; st.rerun()
                    except ValueError as exc: st.error(str(exc))
    st.caption("Independent open-source research integrity software · Not affiliated with GPTZero, Scite, or CiteTrue.")


def dashboard(user):
    st.markdown(f"## Welcome, {user.username}")
    runs = recent_runs(user.id)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Plan", "Superadmin" if user.unlimited else PLANS[user.tier]["name"])
    c2.metric("Credits", "Unlimited" if user.unlimited else f"{user.credits:,}")
    c3.metric("Audits", len(runs)); c4.metric("Version", APP_VERSION)
    if runs:
        st.markdown("### Recent activity")
        st.dataframe(pd.DataFrame([{"date":r.created_at,"citations":r.citation_count,"mode":r.mode,"verified":r.authentic_count,"uncertain":r.unsure_count,"unresolved":r.not_found_count,"integrity":r.average_integrity_score} for r in runs]), use_container_width=True, hide_index=True)
    else: st.info("Your audit history will appear after your first verification.")


def verify_page(user):
    st.markdown("## Verification workspace")
    advanced = tier_allows(user, "researcher"); pro = tier_allows(user, "pro")
    a,b,c = st.columns([1.1,1,1]); deep = a.toggle("Deep Verify", value=advanced, disabled=not advanced); timeout=b.slider("Network timeout",5,30,12); c.metric("Credit cost","1 / citation")
    if not advanced: st.info("Researcher+ unlocks Deep Verify, integrity scoring, retraction/correction intelligence, JSON and PDF reports.")
    uploaded = st.file_uploader("Upload paper or references", type=["txt","bib","ris","pdf","docx","md"])
    pasted = st.text_area("Or paste references", height=190, placeholder="Paste numbered references, APA, BibTeX, RIS, or plain citations...")
    claim = st.text_area("Optional claim/context", height=70, help="For one citation, Pro can screen lexical claim-to-source alignment. This is not an entailment verdict.")
    if st.button("Run verification", type="primary", use_container_width=True):
        text = pasted
        if uploaded:
            suffix=Path(uploaded.name).suffix
            with tempfile.NamedTemporaryFile(delete=False,suffix=suffix) as tmp: tmp.write(uploaded.getvalue()); path=tmp.name
            try: text=extract_text_from_file(path)
            finally: os.unlink(path)
        citations=parse_citations(extract_references_section(text or ""))
        if claim and len(citations)==1: citations[0].context=claim
        if not citations: st.error("No citations detected.")
        else:
            ok,remaining=consume_credits(user.id,len(citations),f"{'Deep' if deep else 'Fast'} verification")
            if not ok: st.error(f"You need {len(citations)} credits; {remaining} remain.")
            else:
                bar=st.progress(0,text="Building evidence graph..."); results=[]
                try:
                    engine=VerificationEngine(timeout=timeout,mailto=user.email)
                    for i,citation in enumerate(citations,1): results.append(engine.verify(citation,deep=deep)); bar.progress(i/len(citations),text=f"Verified {i}/{len(citations)}")
                    st.session_state["results"]=results; record_run(user.id,results,"deep" if deep else "fast")
                except Exception as exc:
                    refund_credits(user.id,len(citations),"Automatic refund after verification error"); st.error(f"Verification failed; credits refunded. {exc}")
                finally: bar.empty()
    results=st.session_state.get("results",[])
    if not results: return
    verified=sum(r.assessment.startswith("authentic") for r in results); unsure=sum(r.assessment=="unsure" for r in results); missing=sum(r.assessment=="not_found" for r in results); avg=round(sum(r.integrity_score for r in results)/len(results))
    m=st.columns(5); m[0].metric("References",len(results));m[1].metric("Verified",verified);m[2].metric("Uncertain",unsure);m[3].metric("Unresolved",missing);m[4].metric("Integrity",f"{avg}/100" if advanced else "Premium")
    rows=[flatten(r) for r in results]
    columns=["index","assessment","confidence","cited_title","matched_title","matched_source"] + (["integrity_score","risk_level","failure_modes","corroborating_sources"] if advanced else [])
    st.dataframe(pd.DataFrame(rows)[columns],use_container_width=True,hide_index=True)
    for r in results:
        with st.expander(f"[{r.citation.index}] {r.assessment.replace('_',' ').title()} · {r.confidence}% confidence"):
            st.write(r.citation.raw)
            if r.matched:
                x=st.columns(4);x[0].metric("Metadata match",f"{r.metadata_consistency}%");x[1].metric("Corroborating indexes",len(r.corroborating_sources));x[2].metric("Citations",r.matched.citation_count if r.matched.citation_count is not None else "—");x[3].metric("Open access","Yes" if r.matched.is_open_access else "Unknown/No")
                st.markdown(f"**Best match:** {r.matched.title}"); st.caption(f"{', '.join(r.matched.authors[:5]) or 'Authors unavailable'} · {r.matched.year or 'n.d.'} · {r.matched.venue or r.matched.source}")
                if r.matched.doi: st.code(r.matched.doi,language=None)
                if r.matched.url: st.link_button("Open matched record",r.matched.url)
            if r.notices: st.warning("\n\n".join(r.notices))
            if advanced:
                q=st.columns(2);q[0].metric("Research Integrity Score",f"{r.integrity_score}/100");q[1].markdown(f"**Risk:** <span class='cg-{r.risk_level}'>{r.risk_level.upper()}</span>",unsafe_allow_html=True)
                if r.failure_modes: st.markdown("**Integrity signals:** "+", ".join(x.replace("_"," ") for x in r.failure_modes))
            else: st.markdown('<div class="cg-lock">🔒 Research Integrity Score, failure taxonomy, post-publication intelligence and provenance analysis are Researcher+ features.</div>',unsafe_allow_html=True)
            if pro and r.support_score is not None: st.metric("Claim-to-source alignment",f"{r.support_score}%");st.caption(r.support_note)
            if pro and r.amalgamation_risk: st.error("Citation Fingerprint warning: different citation components appear to align with different real records. Manual review is strongly recommended.")
            if r.alternatives:
                st.markdown("**Nearby real records**")
                for alt in r.alternatives[:5]: st.write(f"• {alt.title} ({alt.year or 'n.d.'}) — {alt.source} — {alt.doi or alt.url or ''}")
    d=st.columns(3);d[0].download_button("Download CSV",pd.DataFrame(rows).to_csv(index=False).encode(),"citeguard-report.csv","text/csv",use_container_width=True)
    if advanced:
        d[1].download_button("Download JSON",json.dumps([r.to_dict() for r in results],indent=2).encode(),"citeguard-report.json","application/json",use_container_width=True)
        with tempfile.NamedTemporaryFile(suffix=".pdf",delete=False) as tmp: pdf=tmp.name
        try: export_pdf(results,pdf); data=Path(pdf).read_bytes()
        finally: os.unlink(pdf)
        d[2].download_button("Download PDF",data,"citeguard-report.pdf","application/pdf",use_container_width=True)
    else: d[1].button("JSON · Researcher+",disabled=True,use_container_width=True);d[2].button("PDF · Researcher+",disabled=True,use_container_width=True)


def finder_page(user):
    st.markdown("## Evidence & Citation Finder"); st.caption("Find real scholarly records from a topic, title fragment, DOI, or claim.")
    query=st.text_input("What are you researching?",placeholder="e.g., hallucinated citations in LLM-generated scientific writing")
    cap=20 if tier_allows(user,"pro") else 8; limit=st.slider("Results",3,cap,min(8,cap))
    if st.button("Search evidence",type="primary") and query:
        with st.spinner("Searching independent scholarly indexes..."): found=VerificationEngine(mailto=user.email).find(query,limit)
        for i,c in enumerate(found,1):
            with st.container(border=True):
                st.markdown(f"### {i}. {c.title}");st.caption(f"{', '.join(c.authors[:5]) or 'Authors unavailable'} · {c.year or 'n.d.'} · {c.source}")
                z=st.columns(3);z[0].metric("Citations",c.citation_count if c.citation_count is not None else "—");z[1].metric("Open access","Yes" if c.is_open_access else "Unknown/No");z[2].metric("Type",c.publication_type or "—")
                if c.doi: st.code(c.doi,language=None)
                if c.url: st.link_button("Open record",c.url)


def integrity_page(user):
    st.markdown("## Research Integrity Lab")
    if not tier_allows(user,"researcher"): st.markdown('<div class="cg-lock">🔒 Upgrade to Researcher for integrity scoring, retraction/correction intelligence and citation failure taxonomy.</div>',unsafe_allow_html=True);return
    st.markdown("""
CiteGuard separates **unresolved references**, **identifier mismatches**, **title/author/year/venue mismatches**, **possible composite citations**, and **post-publication changes** such as retractions or corrections. Pro additionally exposes Citation Fingerprint and optional claim-to-source alignment screening.

The Research Integrity Score is a triage signal for review prioritization. It is not a misconduct accusation or a substitute for reading the cited work.
""")


def pricing_page(user):
    st.markdown("## Plans & credits"); st.caption("One verification credit is consumed per citation. Superadmin access is unlimited.")
    plan_cards("enterprise" if user.unlimited else user.tier,interactive=True)
    if not billing_configured(): st.info("Secure Stripe checkout is not connected yet. Entitlements are active; checkout buttons will appear after Stripe products/payment links are configured.")


def admin_page(user):
    if not user.is_superadmin: st.error("Superadmin access required.");return
    st.markdown("## Superadmin console"); stats=admin_stats(); c=st.columns(4);c[0].metric("Users",stats["users"]);c[1].metric("Runs",stats["runs"]);c[2].metric("Citations checked",stats["citations"]);c[3].metric("Billing","Connected" if billing_configured() else "Pending")
    st.success("Your superadmin account has unlimited access to all premium capabilities.")
    users=list_users(100)
    if users: st.dataframe(pd.DataFrame([{"username":u.username,"email":u.email,"role":u.role,"tier":u.tier,"credits":"Unlimited" if u.unlimited else u.credits,"active":u.active,"created":u.created_at} for u in users]),use_container_width=True,hide_index=True)
    if not os.getenv("DATABASE_URL"): st.warning("A managed production database is not attached yet. SQLite on free hosting is not durable enough for paid customer accounts. Attach PostgreSQL before accepting payments.")


def shell(user):
    with st.sidebar:
        st.markdown("# 🛡️ CiteGuard");st.caption(f"Research Integrity Platform · v{APP_VERSION}");st.divider();st.markdown(f"**{user.username}**");st.caption(user.email);st.markdown(f"**Plan:** {'Superadmin' if user.unlimited else PLANS[user.tier]['name']}");st.markdown(f"**Credits:** {'Unlimited' if user.unlimited else f'{user.credits:,}'}");st.divider()
        pages=["Dashboard","Verify","Citation Finder","Integrity Lab","Pricing"]+(["Admin"] if user.is_superadmin else []); page=st.radio("Navigate",pages,label_visibility="collapsed");st.divider()
        if st.button("Sign out",use_container_width=True): st.session_state.pop("user_id",None);st.session_state.pop("results",None);st.rerun()
        st.caption("Evidence-first. Human-reviewed decisions.")
    {"Dashboard":dashboard,"Verify":verify_page,"Citation Finder":finder_page,"Integrity Lab":integrity_page,"Pricing":pricing_page,"Admin":admin_page}[page](user)


token=st.query_params.get("reset_token")
if token: reset_screen(token)
else:
    uid=st.session_state.get("user_id"); user=get_user(uid) if uid else None
    shell(user) if user else public_site()

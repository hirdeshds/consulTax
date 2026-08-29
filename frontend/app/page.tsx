"use client";

import { ChangeEvent, FormEvent, useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

type TaxResult = {
  gross_income: number; taxable_income: number; total_tax: number; tax_paid: number; payable: number; refund: number;
  regime: string; rule_version: string; standard_deduction: number; deductions_claimed: number;
  deduction_breakdown: Record<string, number>; excluded_income: Record<string, number>; trace: string[];
};
type Recommendation = { section: string; title: string; potential_deduction: number | null; estimated_tax_saving: number | null; reason: string; conditions: string };
type Analysis = {
  session_id: string; explanation: string; warnings: string[]; result: TaxResult;
  comparison: { new: TaxResult; old: TaxResult; recommended_regime: string; estimated_savings: number; reason: string };
  recommendations: Recommendation[];
};
type Form16Summary = { summary: string; summary_source: string; key_figures: Record<string, string>; explainers: { term: string; meaning: string }[]; warnings: string[]; retrieved_chunks: number };

const money = (value: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value || 0);
const inputNumber = (form: FormData, name: string) => Number(form.get(name) || 0);

function MoneyInput({ name, label, hint, defaultValue = 0 }: { name: string; label: string; hint?: string; defaultValue?: number }) {
  return <label className="field"><span>{label}</span>{hint && <small>{hint}</small>}<div className="currency-input"><i>₹</i><input name={name} type="number" min="0" step="1" defaultValue={defaultValue} /></div></label>;
}

function Toggle({ name, label, defaultChecked = false }: { name: string; label: string; defaultChecked?: boolean }) {
  return <label className="toggle"><input name={name} type="checkbox" defaultChecked={defaultChecked} /><span aria-hidden="true" /><b>{label}</b></label>;
}

export default function Home() {
  const [data, setData] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("");
  const [reply, setReply] = useState("");
  const [form16, setForm16] = useState<Form16Summary | null>(null);
  const [documentError, setDocumentError] = useState("");
  const [uploading, setUploading] = useState(false);
  const uploadRef = useRef<HTMLInputElement>(null);

  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setLoading(true); setError("");
    const form = new FormData(event.currentTarget);
    const profile = {
      name: String(form.get("name") || "Taxpayer"), financial_year: form.get("financial_year"), age: inputNumber(form, "age"),
      is_resident: form.get("is_resident") === "on", residential_location: form.get("residential_location"),
      dependent_parents: form.get("dependent_parents") === "on", parent_is_senior: form.get("parent_is_senior") === "on", children_count: inputNumber(form, "children_count"),
      employment_income: inputNumber(form, "employment_income"), business_revenue: inputNumber(form, "business_revenue"), business_expenses: inputNumber(form, "business_expenses"),
      other_income: inputNumber(form, "other_income"), rental_income: inputNumber(form, "rental_income"), dividend_income: inputNumber(form, "dividend_income"), capital_gains: inputNumber(form, "capital_gains"),
      basic_salary: inputNumber(form, "basic_salary"), hra_received: inputNumber(form, "hra_received"), annual_rent_paid: inputNumber(form, "annual_rent_paid"),
      provident_fund: inputNumber(form, "provident_fund"), elss_investment: inputNumber(form, "elss_investment"), life_insurance_premium: inputNumber(form, "life_insurance_premium"), children_tuition_fees: inputNumber(form, "children_tuition_fees"),
      health_insurance_self_family: inputNumber(form, "health_insurance_self_family"), health_insurance_parents: inputNumber(form, "health_insurance_parents"), parent_medical_spend: inputNumber(form, "parent_medical_spend"),
      home_loan_principal: inputNumber(form, "home_loan_principal"), home_loan_interest: inputNumber(form, "home_loan_interest"), education_loan_interest: inputNumber(form, "education_loan_interest"),
      eligible_medical_treatment: inputNumber(form, "eligible_medical_treatment"), charity_donations: inputNumber(form, "charity_donations"), tax_paid: inputNumber(form, "tax_paid"), regime: "new",
    };
    try {
      const response = await fetch(`${API_URL}/analyze`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "We could not calculate your estimate.");
      setData(body); setReply("");
      document.getElementById("your-plan")?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) { setError(err instanceof Error ? err.message : "Something went wrong."); }
    finally { setLoading(false); }
  }

  async function ask() {
    if (!data || !question.trim()) return;
    const response = await fetch(`${API_URL}/qa`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: data.session_id, question }) });
    const body = await response.json(); setReply(body.answer || body.detail || "I could not answer that question.");
  }

  async function uploadForm16(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true); setDocumentError(""); setForm16(null);
    const payload = new FormData(); payload.append("file", file);
    try {
      const response = await fetch(`${API_URL}/form16/summary`, { method: "POST", body: payload });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "We could not read that PDF.");
      setForm16(body);
    } catch (err) { setDocumentError(err instanceof Error ? err.message : "Could not summarize the document."); }
    finally { setUploading(false); }
  }

  const activeResult = data?.comparison[data.comparison.recommended_regime as "new" | "old"];

  return <main>
    <nav><a className="brand" href="#top">Consul<span>Tax</span><em>Personal tax clarity</em></a><div><a href="#planner">Planner</a><a href="#form16">Form 16</a><button className="nav-cta" onClick={() => document.getElementById("planner")?.scrollIntoView({ behavior: "smooth" })}>Build my plan <span>→</span></button></div></nav>

    <section id="top" className="hero">
      <div className="hero-copy"><span className="eyebrow">INDIA · FY 2024–25 TO 2026–27</span><h1>Make every tax decision <i>make sense.</i></h1><p>One personal dashboard for your income, family, investments and liabilities—then a transparent comparison of the tax regimes and the actions that may matter to you.</p><div className="trust-row"><span>◉ Rules-led math</span><span>◌ Reasoning shown</span><span>▣ Private session</span></div></div>
      <aside className="hero-panel"><div className="panel-top"><span>YOUR TAX MAP</span><b>01</b></div><div className="map-line"><i className="map-dot active" /><span>Tell us about your profile</span></div><div className="map-line"><i className="map-dot" /><span>Compare old and new regimes</span></div><div className="map-line"><i className="map-dot" /><span>Understand every suggestion</span></div><div className="panel-caption">No hidden score. Just rules, numbers and context.</div></aside>
    </section>

    <section className="method"><span className="eyebrow">HOW IT WORKS</span><div><h2>Your information becomes a <i>traceable tax plan.</i></h2><p>We calculate ordinary income and eligible deductions deterministically. An optional AI layer only turns the grounded result or Form 16 text into plain English—it never decides your tax amount.</p></div></section>

    <section id="planner" className="planner-layout">
      <form className="profile-form" onSubmit={analyze}>
        <div className="form-heading"><span className="step-no">01</span><div><span className="eyebrow">YOUR PROFILE</span><h2>Start with the complete picture.</h2></div></div>
        <div className="identity-row"><label className="field"><span>Your name</span><input name="name" defaultValue="Aarav Sharma" required /></label><label className="field"><span>Financial year</span><select name="financial_year" defaultValue="2026-27"><option value="2024-25">FY 2024–25</option><option value="2025-26">FY 2025–26</option><option value="2026-27">FY 2026–27</option></select></label></div>

        <details className="form-section" open><summary><span><b>01</b> About you & your family</span><i>+</i></summary><div className="section-body"><div className="three"><label className="field"><span>Age</span><input name="age" type="number" min="18" max="120" defaultValue="32" required /></label><label className="field"><span>Residential location</span><select name="residential_location" defaultValue="metro"><option value="metro">Metro city</option><option value="non_metro">Non-metro city</option></select></label><label className="field"><span>Children</span><input name="children_count" type="number" min="0" defaultValue="0" /></label></div><div className="toggles"><Toggle name="is_resident" label="Indian resident for tax purposes" defaultChecked /><Toggle name="dependent_parents" label="I support dependent parents" /><Toggle name="parent_is_senior" label="A parent is 60 or older" /></div></div></details>

        <details className="form-section" open><summary><span><b>02</b> Financial profile</span><i>+</i></summary><div className="section-body"><div className="two"><MoneyInput name="employment_income" label="Gross annual salary" defaultValue={1200000} /><MoneyInput name="business_revenue" label="Business revenue" hint="Planning input; revenue alone is not taxable income" /></div><div className="two"><MoneyInput name="business_expenses" label="Business expenses" hint="Used to derive business profit" /><MoneyInput name="other_income" label="Interest / other income" defaultValue={30000} /></div><div className="two"><MoneyInput name="rental_income" label="Rental income" /><MoneyInput name="dividend_income" label="Dividend income" /></div><MoneyInput name="capital_gains" label="Capital gains" hint="Recorded separately until asset type and holding period are known" /></div></details>

        <details className="form-section"><summary><span><b>03</b> Investments, insurance & giving</span><i>+</i></summary><div className="section-body"><p className="section-note">These are considered for the old-regime comparison only, subject to eligibility and the limits shown in your result.</p><div className="two"><MoneyInput name="provident_fund" label="Provident fund contributions" /><MoneyInput name="elss_investment" label="ELSS investments" /></div><div className="two"><MoneyInput name="life_insurance_premium" label="Life-insurance premium" /><MoneyInput name="children_tuition_fees" label="Eligible children’s tuition fees" /></div><div className="two"><MoneyInput name="health_insurance_self_family" label="Health insurance: self/family" /><MoneyInput name="health_insurance_parents" label="Health insurance: parents" /></div><div className="two"><MoneyInput name="parent_medical_spend" label="Eligible parent medical spend" hint="Only relevant for an uninsured senior parent" /><MoneyInput name="charity_donations" label="Eligible charity donation" hint="This model uses the 50%-deduction category" /></div></div></details>

        <details className="form-section"><summary><span><b>04</b> Home, education & medical liabilities</span><i>+</i></summary><div className="section-body"><div className="two"><MoneyInput name="home_loan_principal" label="Home-loan principal repaid" /><MoneyInput name="home_loan_interest" label="Home-loan interest paid" /></div><div className="two"><MoneyInput name="education_loan_interest" label="Eligible education-loan interest" /><MoneyInput name="eligible_medical_treatment" label="Eligible recurring treatment" hint="Section 80DDB; certificate required" /></div></div></details>

        <details className="form-section"><summary><span><b>05</b> Salary exemptions & tax paid</span><i>+</i></summary><div className="section-body"><div className="two"><MoneyInput name="basic_salary" label="Basic salary" /><MoneyInput name="hra_received" label="HRA received" /></div><div className="two"><MoneyInput name="annual_rent_paid" label="Annual rent paid" /><MoneyInput name="tax_paid" label="Tax already paid / TDS" defaultValue={20000} /></div></div></details>
        <button className="calculate" disabled={loading}>{loading ? "Building your plan…" : <><span>See my personalised plan</span><b>→</b></>}</button>{error && <p className="error">{error}</p>}
        <p className="form-disclaimer">Indicative calculation for planning, not a filing or certified tax opinion.</p>
      </form>

      <aside id="your-plan" className="results">
        {!data ? <div className="result-placeholder"><span className="result-orb">₹</span><span className="eyebrow">YOUR PERSONAL VIEW</span><h2>We’ll turn your details into a clear next step.</h2><p>Compare regimes, see the deduction rules actually used, and understand what needs a closer look.</p><div className="placeholder-list"><span><b>1</b> Tax under both regimes</span><span><b>2</b> Personalised possibilities</span><span><b>3</b> Reasoning behind each number</span></div></div> : <>
          <div className="result-head"><span className="eyebrow">YOUR PERSONAL TAX PLAN</span><span className="rule-tag">{activeResult?.rule_version}</span></div>
          <div className="recommendation-hero"><span>Recommended route</span><h2>{data.comparison.recommended_regime === "new" ? "New regime" : "Old regime"}</h2><p>{data.comparison.reason}</p><strong>{money(data.comparison.estimated_savings)} <small>lower estimated tax</small></strong></div>
          <div className="regime-cards"><div className={data.comparison.recommended_regime === "new" ? "regime selected" : "regime"}><span>NEW</span><b>{money(data.comparison.new.total_tax)}</b><small>Total tax incl. cess</small></div><div className={data.comparison.recommended_regime === "old" ? "regime selected" : "regime"}><span>OLD</span><b>{money(data.comparison.old.total_tax)}</b><small>Total tax incl. cess</small></div></div>
          <div className="outcome-row"><div><span>{data.result.payable ? "Estimated still payable" : "Estimated refund"}</span><b>{money(data.result.payable || data.result.refund)}</b></div><div><span>Taxable ordinary income</span><b>{money(data.result.taxable_income)}</b></div></div>
          <p className="primary-reason">{data.explanation}</p>
          {data.warnings.length > 0 && <div className="warnings">{data.warnings.map(warning => <p key={warning}>! {warning}</p>)}</div>}
          <div className="reasoning"><div className="reasoning-title"><span className="eyebrow">WHY THESE SUGGESTIONS APPEAR</span><h3>Personalised possibilities</h3></div>{data.recommendations.length ? data.recommendations.map(item => <article className="opportunity" key={`${item.section}-${item.title}`}><div className="opportunity-head"><span>{item.section}</span>{item.estimated_tax_saving !== null && <b>Up to {money(item.estimated_tax_saving)}</b>}</div><h4>{item.title}</h4>{item.potential_deduction !== null && <p className="deduction">Potential eligible reduction: {money(item.potential_deduction)}</p>}<p>{item.reason}</p><small>{item.conditions}</small></article>) : <p className="no-opportunities">No extra rule-based opportunities were identified from the information provided. Expand a section to add any relevant details.</p>}</div>
          <details className="calculation-trace"><summary>Show the calculation & rule trace <span>↓</span></summary><div><p><b>Eligible reductions used:</b> {money(data.result.deductions_claimed)}</p>{Object.entries(data.result.deduction_breakdown).map(([label, value]) => <p key={label}>{label}: <b>{money(value)}</b></p>)}{data.result.trace.map(step => <p key={step}>{step}</p>)}</div></details>
          <div className="qa"><label>Ask about this calculation<input value={question} onChange={e => setQuestion(e.target.value)} placeholder="Why is the new regime recommended?" onKeyDown={e => e.key === "Enter" && ask()} /></label><button onClick={ask}>Ask <span>→</span></button>{reply && <p>{reply}</p>}</div>
        </>}
      </aside>
    </section>

    <section id="form16" className="form16-section"><div className="form16-copy"><span className="eyebrow">FORM 16, EXPLAINED</span><h2>Your salary document, <i>without the jargon.</i></h2><p>Upload a text-based Form 16 PDF. We retrieve the relevant document sections, extract key figures and explain what they mean in everyday language.</p><ul><li>Gross salary, deductions and taxable income</li><li>TDS explained as a credit you can verify</li><li>Important gaps to check before filing</li></ul><p className="privacy-note">Your document is processed for this summary and is not stored as a permanent profile.</p></div><div className="upload-card"><input ref={uploadRef} type="file" accept="application/pdf" onChange={uploadForm16} hidden /><button className="drop-zone" onClick={() => uploadRef.current?.click()} disabled={uploading}><span className="upload-icon">⇧</span><b>{uploading ? "Reading your Form 16…" : "Upload Form 16 PDF"}</b><small>Text-based PDF · maximum 8 MB</small></button>{documentError && <p className="error">{documentError}</p>}{form16 && <div className="document-result"><div className="doc-label"><span>FORM 16 SUMMARY</span><small>{form16.summary_source}</small></div><p className="doc-summary">{form16.summary}</p>{Object.keys(form16.key_figures).length > 0 && <div className="doc-figures">{Object.entries(form16.key_figures).map(([label, value]) => <div key={label}><span>{label}</span><b>{value}</b></div>)}</div>}<details><summary>What these terms mean</summary>{form16.explainers.map(item => <p key={item.term}><b>{item.term}:</b> {item.meaning}</p>)}</details>{form16.warnings.map(warning => <p className="doc-warning" key={warning}>! {warning}</p>)}</div>}</div></section>
    <footer><div className="brand">Consul<span>Tax</span></div><p>Rules-based planning for Indian individual taxpayers. Always verify eligibility and filing details before submitting an ITR.</p><span>© 2026</span></footer>
  </main>;
}

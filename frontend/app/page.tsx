"use client";

import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://consultax.onrender.com/api";

type SchemeCardData = {
  scheme_id: string;
  section: string;
  name: string;
  category: string;
  status: "claimed" | "partially_claimed" | "untapped" | "not_applicable";
  claimed_amount: number;
  max_limit: number | null;
  potential_deduction: number;
  estimated_tax_saving: number;
  trigger_rule: string;
  plain_explanation: string;
  eligibility_conditions: string;
};

type TaxResult = {
  gross_income: number;
  taxable_income: number;
  income_tax: number;
  rebate: number;
  surcharge: number;
  surcharge_marginal_relief: number;
  cess: number;
  total_tax: number;
  tax_paid: number;
  payable: number;
  refund: number;
  regime: string;
  rule_version: string;
  standard_deduction: number;
  deductions_claimed: number;
  deduction_breakdown: Record<string, number>;
  excluded_income: Record<string, number>;
  schemes: SchemeCardData[];
  trace: string[];
};

type Recommendation = {
  section: string;
  title: string;
  potential_deduction: number | null;
  estimated_tax_saving: number | null;
  reason: string;
  conditions: string;
};

type Analysis = {
  session_id: string;
  profile: Record<string, any>;
  explanation: string;
  warnings: string[];
  result: TaxResult;
  comparison: {
    new: TaxResult;
    old: TaxResult;
    recommended_regime: string;
    estimated_savings: number;
    reason: string;
  };
  recommendations: Recommendation[];
};

type Form16Summary = {
  summary: string;
  summary_source: string;
  key_figures: Record<string, string>;
  mapped_profile?: Record<string, any>;
  explainers: { term: string; meaning: string }[];
  warnings: string[];
  retrieved_chunks: number;
};

type SampleDoc = {
  id: string;
  title: string;
  document_type: string;
  description: string;
  text_content: string;
  mapped_profile: Record<string, any>;
};

const money = (value: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value || 0);

export default function Home() {
  const [data, setData] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("");
  const [reply, setReply] = useState("");
  const [qaLoading, setQaLoading] = useState(false);
  const [form16, setForm16] = useState<Form16Summary | null>(null);
  const [documentError, setDocumentError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [sampleDocs, setSampleDocs] = useState<SampleDoc[]>([]);
  const [selectedSampleDocId, setSelectedSampleDocId] = useState<string>("");
  const [rulesConfig, setRulesConfig] = useState<Record<string, any> | null>(null);
  const [activeRuleYear, setActiveRuleYear] = useState<string>("2025-26");
  const [activeTab, setActiveTab] = useState<"planner" | "schemes" | "rules" | "form16">("planner");
  
  // Simulator State
  const [simNps, setSimNps] = useState<number>(0);
  const [simHealthParents, setSimHealthParents] = useState<number>(0);
  const [simDonations, setSimDonations] = useState<number>(0);
  const [simulating, setSimulating] = useState(false);

  const formRef = useRef<HTMLFormElement>(null);
  const uploadRef = useRef<HTMLInputElement>(null);

  // Initial Form Profile State
  const [profileState, setProfileState] = useState({
    name: "Aarav Sharma",
    financial_year: "2025-26",
    age: 32,
    is_resident: true,
    residential_location: "metro",
    dependent_parents: false,
    parent_is_senior: false,
    children_count: 0,
    employment_income: 1500000,
    business_revenue: 0,
    business_expenses: 0,
    other_income: 30000,
    rental_income: 0,
    dividend_income: 0,
    capital_gains: 0,
    basic_salary: 750000,
    hra_received: 150000,
    annual_rent_paid: 180000,
    provident_fund: 100000,
    elss_investment: 50000,
    life_insurance_premium: 0,
    children_tuition_fees: 0,
    nps_tier1_80ccd: 0,
    savings_interest: 15000,
    health_insurance_self_family: 20000,
    health_insurance_parents: 0,
    parent_medical_spend: 0,
    home_loan_principal: 0,
    home_loan_interest: 0,
    education_loan_interest: 0,
    eligible_medical_treatment: 0,
    charity_donations: 0,
    deductions: 0,
    tax_paid: 85000,
    regime: "new" as "new" | "old",
  });

  // Fetch sample documents and rule configs on mount
  useEffect(() => {
    fetch(`${API_URL}/sample-documents`)
      .then((res) => (res.ok ? res.json() : []))
      .then((docs: SampleDoc[]) => {
        setSampleDocs(docs);
        if (docs.length > 0) setSelectedSampleDocId(docs[0].id);
      })
      .catch(() => {});

    fetch(`${API_URL}/rules/config`)
      .then((res) => (res.ok ? res.json() : null))
      .then((configs) => {
        if (configs) setRulesConfig(configs);
      })
      .catch(() => {});
  }, []);

  // Handle Profile Submission
  async function runAnalysis(customProfile?: typeof profileState) {
    setLoading(true);
    setError("");
    const targetProfile = customProfile || profileState;
    try {
      const response = await fetch(`${API_URL}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: targetProfile }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Could not calculate your estimate.");
      setData(body);
      setReply("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  function handleFormSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    runAnalysis();
    document.getElementById("your-plan")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // Load Persona Preset
  function applyPersona(personaKey: string) {
    let newProfile = { ...profileState };
    if (personaKey === "aarav") {
      newProfile = {
        ...newProfile,
        name: "Aarav Sharma (Tech Lead)",
        financial_year: "2025-26",
        age: 32,
        is_resident: true,
        residential_location: "metro",
        dependent_parents: false,
        parent_is_senior: false,
        children_count: 0,
        employment_income: 1885000,
        basic_salary: 900000,
        hra_received: 180000,
        annual_rent_paid: 240000,
        provident_fund: 90000,
        elss_investment: 60000,
        life_insurance_premium: 35000,
        nps_tier1_80ccd: 50000,
        savings_interest: 12000,
        health_insurance_self_family: 25000,
        health_insurance_parents: 0,
        parent_medical_spend: 0,
        home_loan_principal: 0,
        home_loan_interest: 0,
        education_loan_interest: 0,
        eligible_medical_treatment: 0,
        charity_donations: 0,
        tax_paid: 145000,
      };
    } else if (personaKey === "priya") {
      newProfile = {
        ...newProfile,
        name: "Priya Venkat (Senior Caregiver)",
        financial_year: "2025-26",
        age: 38,
        is_resident: true,
        residential_location: "metro",
        dependent_parents: true,
        parent_is_senior: true,
        children_count: 2,
        employment_income: 1450000,
        basic_salary: 700000,
        hra_received: 0,
        annual_rent_paid: 0,
        provident_fund: 70000,
        elss_investment: 0,
        life_insurance_premium: 0,
        children_tuition_fees: 80000,
        nps_tier1_80ccd: 0,
        savings_interest: 18000,
        health_insurance_self_family: 25000,
        health_insurance_parents: 50000,
        parent_medical_spend: 0,
        home_loan_principal: 50000,
        home_loan_interest: 200000,
        education_loan_interest: 0,
        eligible_medical_treatment: 0,
        charity_donations: 10000,
        tax_paid: 65000,
      };
    } else if (personaKey === "rohan") {
      newProfile = {
        ...newProfile,
        name: "Rohan Mehta (Consultant)",
        financial_year: "2025-26",
        age: 29,
        is_resident: true,
        residential_location: "metro",
        dependent_parents: false,
        parent_is_senior: false,
        children_count: 0,
        employment_income: 0,
        business_revenue: 2400000,
        business_expenses: 650000,
        other_income: 45000,
        savings_interest: 10000,
        basic_salary: 0,
        hra_received: 0,
        annual_rent_paid: 0,
        provident_fund: 150000,
        elss_investment: 0,
        life_insurance_premium: 0,
        children_tuition_fees: 0,
        nps_tier1_80ccd: 50000,
        health_insurance_self_family: 15000,
        health_insurance_parents: 0,
        parent_medical_spend: 0,
        home_loan_principal: 0,
        home_loan_interest: 0,
        education_loan_interest: 85000,
        eligible_medical_treatment: 0,
        charity_donations: 0,
        tax_paid: 120000,
      };
    } else if (personaKey === "ramachandran") {
      newProfile = {
        ...newProfile,
        name: "Ramachandran Iyer (Senior Retiree)",
        financial_year: "2025-26",
        age: 68,
        is_resident: true,
        residential_location: "non_metro",
        dependent_parents: false,
        parent_is_senior: false,
        children_count: 0,
        employment_income: 840000,
        business_revenue: 0,
        business_expenses: 0,
        other_income: 95000,
        savings_interest: 95000,
        basic_salary: 0,
        hra_received: 0,
        annual_rent_paid: 0,
        provident_fund: 150000,
        elss_investment: 0,
        life_insurance_premium: 0,
        children_tuition_fees: 0,
        nps_tier1_80ccd: 0,
        health_insurance_self_family: 45000,
        health_insurance_parents: 0,
        parent_medical_spend: 5000,
        home_loan_principal: 0,
        home_loan_interest: 0,
        education_loan_interest: 0,
        eligible_medical_treatment: 0,
        charity_donations: 0,
        tax_paid: 28000,
      };
    }
    setProfileState(newProfile);
    runAnalysis(newProfile);
  }

  // Ask Plain Language QA
  async function ask() {
    if (!data || !question.trim()) return;
    setQaLoading(true);
    try {
      const response = await fetch(`${API_URL}/qa`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: data.session_id, question }),
      });
      const body = await response.json();
      setReply(body.answer || body.detail || "I could not answer that question.");
    } catch {
      setReply("Could not connect to the assistant.");
    } finally {
      setQaLoading(false);
    }
  }

  // Upload Form 16 PDF
  async function uploadForm16(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setDocumentError("");
    setForm16(null);
    const payload = new FormData();
    payload.append("file", file);
    try {
      const response = await fetch(`${API_URL}/form16/summary`, {
        method: "POST",
        body: payload,
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "We could not read that PDF.");
      setForm16(body);
    } catch (err) {
      setDocumentError(err instanceof Error ? err.message : "Could not summarize document.");
    } finally {
      setUploading(false);
    }
  }

  // Parse Selected Clean Sample Document
  async function parseSampleDoc(docId: string) {
    const doc = sampleDocs.find((d) => d.id === docId);
    if (!doc) return;
    setUploading(true);
    setDocumentError("");
    try {
      const response = await fetch(`${API_URL}/document/parse-text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: doc.text_content }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Could not parse sample document.");
      setForm16(body);
    } catch (err) {
      setDocumentError(err instanceof Error ? err.message : "Could not parse sample document.");
    } finally {
      setUploading(false);
    }
  }

  // Apply Parsed Document directly into Planner
  function applyDocumentToPlanner() {
    if (!form16 || !form16.mapped_profile) return;
    const mapped = form16.mapped_profile;
    const updated = {
      ...profileState,
      ...mapped,
    };
    setProfileState(updated);
    setActiveTab("planner");
    runAnalysis(updated);
  }

  // Run Real-time Simulation
  async function simulateChanges() {
    if (!data) return;
    setSimulating(true);
    try {
      const changes: Record<string, number> = {};
      if (simNps > 0) changes["nps_tier1_80ccd"] = profileState.nps_tier1_80ccd + simNps;
      if (simHealthParents > 0) changes["health_insurance_parents"] = profileState.health_insurance_parents + simHealthParents;
      if (simDonations > 0) changes["charity_donations"] = profileState.charity_donations + simDonations;

      const response = await fetch(`${API_URL}/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile: profileState,
          session_id: data.session_id,
          changes,
        }),
      });
      const body = await response.json();
      if (response.ok) {
        setData(body);
      }
    } catch {
      // ignore
    } finally {
      setSimulating(false);
    }
  }

  const activeResult = data?.comparison[data.comparison.recommended_regime as "new" | "old"];
  const currentSchemes = data?.result?.schemes || [];

  return (
    <main>
      {/* Top Persistent Statutory & Privacy Disclaimer */}
      <div className="disclaimer-banner">
        <div className="disclaimer-inner">
          <div className="disclaimer-item">
            <span className="badge-warning">⚠️ STATUTORY NOTICE</span>
            <span>
              <strong>Not a Certified Tax Authority / Chartered Accountant:</strong> ConsulTax provides indicative educational planning and deterministic statutory calculations under the Income Tax Act, 1961. Always consult a tax professional before filing your ITR.
            </span>
          </div>
          <div className="privacy-pill">
            <span className="privacy-dot" />
            <span>100% In-Memory Session · Zero Data Stored</span>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav>
        <a className="brand" href="#top">
          Consul<span>Tax</span>
          <em>Plain-Language Tax Assistant</em>
        </a>
        <div className="nav-links">
          <button
            className={`nav-tab ${activeTab === "planner" ? "active" : ""}`}
            onClick={() => setActiveTab("planner")}
          >
            Tax Planner
          </button>
          <button
            className={`nav-tab ${activeTab === "schemes" ? "active" : ""}`}
            onClick={() => setActiveTab("schemes")}
          >
            8 Govt Schemes
          </button>
          <button
            className={`nav-tab ${activeTab === "rules" ? "active" : ""}`}
            onClick={() => setActiveTab("rules")}
          >
            Rules & Slabs Config
          </button>
          <button
            className={`nav-tab ${activeTab === "form16" ? "active" : ""}`}
            onClick={() => setActiveTab("form16")}
          >
            Sample Documents & Form 16
          </button>
          <button
            className="nav-cta"
            onClick={() => {
              setActiveTab("planner");
              document.getElementById("planner")?.scrollIntoView({ behavior: "smooth" });
            }}
          >
            Build my plan <span>→</span>
          </button>
        </div>
      </nav>

      {/* Hero Section */}
      <section id="top" className="hero">
        <div className="hero-copy">
          <span className="eyebrow">INDIA · DETERMINISTIC TAX ENGINE & PLAIN ENGLISH AI</span>
          <h1>
            Understand your taxes <i>without the jargon.</i>
          </h1>
          <p>
            An AI-powered tax assistant that models your synthetic income and expenses, identifies all eligible deductions, surfaces 8 statutory government savings schemes, and compares Old vs New regimes with transparent mathematical reasoning.
          </p>
          <div className="trust-row">
            <span>◉ Deterministic Math</span>
            <span>◌ 8 Canonical Schemes</span>
            <span>▣ Explainable "Why" Traces</span>
            <span>◈ Zero Data Stored</span>
          </div>
        </div>

        <aside className="hero-panel">
          <div className="panel-top">
            <span>CONSULTAX WORKFLOW</span>
            <b>01 - 04</b>
          </div>
          <div className="map-line">
            <i className="map-dot active" />
            <span>1. Load clean sample document or enter synthetic profile</span>
          </div>
          <div className="map-line">
            <i className="map-dot" />
            <span>2. Deterministic regime comparison & tax liability</span>
          </div>
          <div className="map-line">
            <i className="map-dot" />
            <span>3. Surface 8 government schemes with trigger math</span>
          </div>
          <div className="map-line">
            <i className="map-dot" />
            <span>4. Ask questions & simulate potential tax savings</span>
          </div>
          <div className="panel-caption">
            Rule-driven logic with plain-English grounding. No black box outputs.
          </div>
        </aside>
      </section>

      {/* Synthetic Personas Bar */}
      <section className="personas-bar">
        <div className="personas-header">
          <span className="eyebrow">QUICK TEST SYNTHETIC PERSONAS</span>
          <p>Load 1-click synthetic taxpayer profiles to test rules and scheme eligibility:</p>
        </div>
        <div className="persona-chips">
          <button className="persona-btn" onClick={() => applyPersona("aarav")}>
            <b>💼 Aarav (Tech Lead)</b>
            <small>₹18.85L · EPF, HRA, ELSS, NPS</small>
          </button>
          <button className="persona-btn" onClick={() => applyPersona("priya")}>
            <b>🏡 Priya (Caregiver)</b>
            <small>₹14.5L · Senior Parents, Home Loan, 80D</small>
          </button>
          <button className="persona-btn" onClick={() => applyPersona("rohan")}>
            <b>🎨 Rohan (Consultant)</b>
            <small>₹24L Rev · ₹6.5L Exp, Education Loan</small>
          </button>
          <button className="persona-btn" onClick={() => applyPersona("ramachandran")}>
            <b>👴 Ramachandran (Senior)</b>
            <small>₹8.4L Pension · ₹95k Interest u/s 80TTB</small>
          </button>
        </div>
      </section>

      {/* Main Tab Views */}
      {activeTab === "planner" && (
        <section id="planner" className="planner-layout">
          {/* Tax Profile Form */}
          <form className="profile-form" ref={formRef} onSubmit={handleFormSubmit}>
            <div className="form-heading">
              <span className="step-no">01</span>
              <div>
                <span className="eyebrow">INPUT PROFILE</span>
                <h2>Personal & Financial Details</h2>
              </div>
            </div>

            <div className="identity-row">
              <label className="field">
                <span>Taxpayer name</span>
                <input
                  value={profileState.name}
                  onChange={(e) => setProfileState({ ...profileState, name: e.target.value })}
                  required
                />
              </label>
              <label className="field">
                <span>Financial Year (Editable Rules)</span>
                <select
                  value={profileState.financial_year}
                  onChange={(e) =>
                    setProfileState({ ...profileState, financial_year: e.target.value })
                  }
                >
                  <option value="2024-25">FY 2024–25 (Budget 2024)</option>
                  <option value="2025-26">FY 2025–26 (Budget 2025 - ₹12L Rebate)</option>
                  <option value="2026-27">FY 2026–27 (Budget 2026)</option>
                </select>
              </label>
            </div>

            {/* Section 1: Demographics */}
            <details className="form-section" open>
              <summary>
                <span>
                  <b>01</b> Demographics & Family Context
                </span>
                <i>+</i>
              </summary>
              <div className="section-body">
                <div className="three">
                  <label className="field">
                    <span>Age</span>
                    <input
                      type="number"
                      min="18"
                      max="120"
                      value={profileState.age}
                      onChange={(e) =>
                        setProfileState({ ...profileState, age: Number(e.target.value) || 0 })
                      }
                      required
                    />
                  </label>
                  <label className="field">
                    <span>City Category</span>
                    <select
                      value={profileState.residential_location}
                      onChange={(e) =>
                        setProfileState({
                          ...profileState,
                          residential_location: e.target.value as "metro" | "non_metro",
                        })
                      }
                    >
                      <option value="metro">Metro (Delhi, Mumbai, Kolkata, Chennai)</option>
                      <option value="non_metro">Non-Metro</option>
                    </select>
                  </label>
                  <label className="field">
                    <span>Dependent Children</span>
                    <input
                      type="number"
                      min="0"
                      value={profileState.children_count}
                      onChange={(e) =>
                        setProfileState({
                          ...profileState,
                          children_count: Number(e.target.value) || 0,
                        })
                      }
                    />
                  </label>
                </div>
                <div className="toggles">
                  <label className="toggle">
                    <input
                      type="checkbox"
                      checked={profileState.is_resident}
                      onChange={(e) =>
                        setProfileState({ ...profileState, is_resident: e.target.checked })
                      }
                    />
                    <span />
                    <b>Indian resident for tax purposes</b>
                  </label>
                  <label className="toggle">
                    <input
                      type="checkbox"
                      checked={profileState.dependent_parents}
                      onChange={(e) =>
                        setProfileState({ ...profileState, dependent_parents: e.target.checked })
                      }
                    />
                    <span />
                    <b>I support dependent parents</b>
                  </label>
                  <label className="toggle">
                    <input
                      type="checkbox"
                      checked={profileState.parent_is_senior}
                      onChange={(e) =>
                        setProfileState({ ...profileState, parent_is_senior: e.target.checked })
                      }
                    />
                    <span />
                    <b>A parent is 60 or older</b>
                  </label>
                </div>
              </div>
            </details>

            {/* Section 2: Income Profile */}
            <details className="form-section" open>
              <summary>
                <span>
                  <b>02</b> Income Sources (Salary, Business, Others)
                </span>
                <i>+</i>
              </summary>
              <div className="section-body">
                <div className="two">
                  <label className="field">
                    <span>Gross Annual Salary (Form 16)</span>
                    <div className="currency-input">
                      <i>₹</i>
                      <input
                        type="number"
                        min="0"
                        value={profileState.employment_income}
                        onChange={(e) =>
                          setProfileState({
                            ...profileState,
                            employment_income: Number(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                  </label>
                  <label className="field">
                    <span>Professional / Business Revenue</span>
                    <div className="currency-input">
                      <i>₹</i>
                      <input
                        type="number"
                        min="0"
                        value={profileState.business_revenue}
                        onChange={(e) =>
                          setProfileState({
                            ...profileState,
                            business_revenue: Number(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                  </label>
                </div>

                <div className="two">
                  <label className="field">
                    <span>Allowable Business / Professional Expenses</span>
                    <div className="currency-input">
                      <i>₹</i>
                      <input
                        type="number"
                        min="0"
                        value={profileState.business_expenses}
                        onChange={(e) =>
                          setProfileState({
                            ...profileState,
                            business_expenses: Number(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                  </label>
                  <label className="field">
                    <span>Savings / FD / Other Interest Income</span>
                    <small>Eligible for Section 80TTA / 80TTB deduction</small>
                    <div className="currency-input">
                      <i>₹</i>
                      <input
                        type="number"
                        min="0"
                        value={profileState.savings_interest}
                        onChange={(e) =>
                          setProfileState({
                            ...profileState,
                            savings_interest: Number(e.target.value) || 0,
                            other_income: Number(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                  </label>
                </div>
              </div>
            </details>

            {/* Section 3: Schemes & Deductions */}
            <details className="form-section" open>
              <summary>
                <span>
                  <b>03</b> Deductions & Government Schemes (Old Regime)
                </span>
                <i>+</i>
              </summary>
              <div className="section-body">
                <div className="two">
                  <label className="field">
                    <span>Section 80C: EPF, PPF, ELSS, Life Insurance</span>
                    <small>Capped at ₹1,50,000</small>
                    <div className="currency-input">
                      <i>₹</i>
                      <input
                        type="number"
                        min="0"
                        value={profileState.provident_fund}
                        onChange={(e) =>
                          setProfileState({
                            ...profileState,
                            provident_fund: Number(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                  </label>
                  <label className="field">
                    <span>Section 80CCD(1B): NPS Tier-1 Contribution</span>
                    <small>Exclusive ₹50,000 allowance over 80C</small>
                    <div className="currency-input">
                      <i>₹</i>
                      <input
                        type="number"
                        min="0"
                        value={profileState.nps_tier1_80ccd}
                        onChange={(e) =>
                          setProfileState({
                            ...profileState,
                            nps_tier1_80ccd: Number(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                  </label>
                </div>

                <div className="two">
                  <label className="field">
                    <span>Section 80D: Self & Family Health Insurance</span>
                    <small>Limit: ₹25,000 (₹50,000 if senior)</small>
                    <div className="currency-input">
                      <i>₹</i>
                      <input
                        type="number"
                        min="0"
                        value={profileState.health_insurance_self_family}
                        onChange={(e) =>
                          setProfileState({
                            ...profileState,
                            health_insurance_self_family: Number(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                  </label>
                  <label className="field">
                    <span>Section 80D: Parents Health Insurance & Medical</span>
                    <small>Limit: ₹25,000 (₹50,000 if senior parent)</small>
                    <div className="currency-input">
                      <i>₹</i>
                      <input
                        type="number"
                        min="0"
                        value={profileState.health_insurance_parents}
                        onChange={(e) =>
                          setProfileState({
                            ...profileState,
                            health_insurance_parents: Number(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                  </label>
                </div>

                <div className="two">
                  <label className="field">
                    <span>Section 24(b): Home Loan Interest (Self-Occupied)</span>
                    <small>Capped at ₹2,00,000</small>
                    <div className="currency-input">
                      <i>₹</i>
                      <input
                        type="number"
                        min="0"
                        value={profileState.home_loan_interest}
                        onChange={(e) =>
                          setProfileState({
                            ...profileState,
                            home_loan_interest: Number(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                  </label>
                  <label className="field">
                    <span>Section 80E: Higher Education Loan Interest</span>
                    <small>100% deduction with no upper cap</small>
                    <div className="currency-input">
                      <i>₹</i>
                      <input
                        type="number"
                        min="0"
                        value={profileState.education_loan_interest}
                        onChange={(e) =>
                          setProfileState({
                            ...profileState,
                            education_loan_interest: Number(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                  </label>
                </div>

                <div className="two">
                  <label className="field">
                    <span>Section 80G: Eligible Charitable Donations</span>
                    <small>50% deduction category with qualifying limits</small>
                    <div className="currency-input">
                      <i>₹</i>
                      <input
                        type="number"
                        min="0"
                        value={profileState.charity_donations}
                        onChange={(e) =>
                          setProfileState({
                            ...profileState,
                            charity_donations: Number(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                  </label>
                  <label className="field">
                    <span>Section 80DDB: Critical Illness Medical Treatment</span>
                    <small>Limit: ₹40,000 (₹1,00,000 for senior citizens)</small>
                    <div className="currency-input">
                      <i>₹</i>
                      <input
                        type="number"
                        min="0"
                        value={profileState.eligible_medical_treatment}
                        onChange={(e) =>
                          setProfileState({
                            ...profileState,
                            eligible_medical_treatment: Number(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                  </label>
                </div>
              </div>
            </details>

            {/* Section 4: HRA & Taxes Paid */}
            <details className="form-section">
              <summary>
                <span>
                  <b>04</b> Salary Exemptions (HRA) & TDS Paid
                </span>
                <i>+</i>
              </summary>
              <div className="section-body">
                <div className="three">
                  <label className="field">
                    <span>Basic Salary</span>
                    <div className="currency-input">
                      <i>₹</i>
                      <input
                        type="number"
                        min="0"
                        value={profileState.basic_salary}
                        onChange={(e) =>
                          setProfileState({
                            ...profileState,
                            basic_salary: Number(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                  </label>
                  <label className="field">
                    <span>HRA Received</span>
                    <div className="currency-input">
                      <i>₹</i>
                      <input
                        type="number"
                        min="0"
                        value={profileState.hra_received}
                        onChange={(e) =>
                          setProfileState({
                            ...profileState,
                            hra_received: Number(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                  </label>
                  <label className="field">
                    <span>Annual Rent Paid</span>
                    <div className="currency-input">
                      <i>₹</i>
                      <input
                        type="number"
                        min="0"
                        value={profileState.annual_rent_paid}
                        onChange={(e) =>
                          setProfileState({
                            ...profileState,
                            annual_rent_paid: Number(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                  </label>
                </div>
                <label className="field">
                  <span>TDS / Advance Tax Paid (Credit)</span>
                  <div className="currency-input">
                    <i>₹</i>
                    <input
                      type="number"
                      min="0"
                      value={profileState.tax_paid}
                      onChange={(e) =>
                        setProfileState({
                          ...profileState,
                          tax_paid: Number(e.target.value) || 0,
                        })
                      }
                    />
                  </div>
                </label>
              </div>
            </details>

            <button className="calculate" type="submit" disabled={loading}>
              {loading ? "Calculating Tax & Scheme Rules…" : (
                <>
                  <span>Calculate & Compare Regimes</span>
                  <b>→</b>
                </>
              )}
            </button>
            {error && <p className="error">{error}</p>}
          </form>

          {/* Results Column */}
          <aside id="your-plan" className="results">
            {!data ? (
              <div className="result-placeholder">
                <span className="result-orb">₹</span>
                <span className="eyebrow">INSTANT TAX CLARITY</span>
                <h2>Calculate and Compare Both Regimes with Deterministic Trace</h2>
                <p>
                  Submit the form or click any synthetic persona above to view side-by-side New vs Old regime tax computations, eligible scheme savings, and plain-English explainers.
                </p>
                <div className="placeholder-list">
                  <span>
                    <b>1</b> Transparent Slab Math & 87A Rebates
                  </span>
                  <span>
                    <b>2</b> 8 Canonical Government Schemes Surfaced
                  </span>
                  <span>
                    <b>3</b> Grounded Q&A Assistant
                  </span>
                </div>
              </div>
            ) : (
              <>
                <div className="result-head">
                  <span className="eyebrow">PERSONALIZED TAX ASSESSMENT</span>
                  <span className="rule-tag">{activeResult?.rule_version}</span>
                </div>

                {/* Regime Recommendation Hero */}
                <div className="recommendation-hero">
                  <span>OPTIMAL TAX ROUTE</span>
                  <h2>
                    {data.comparison.recommended_regime === "new"
                      ? "New Tax Regime"
                      : "Old Tax Regime"}
                  </h2>
                  <p>{data.comparison.reason}</p>
                  <strong>
                    {money(data.comparison.estimated_savings)}{" "}
                    <small>lower estimated tax liability</small>
                  </strong>
                </div>

                {/* Regime Comparison Cards */}
                <div className="regime-cards">
                  <div
                    className={
                      data.comparison.recommended_regime === "new"
                        ? "regime selected"
                        : "regime"
                    }
                  >
                    <span>NEW REGIME</span>
                    <b>{money(data.comparison.new.total_tax)}</b>
                    <small>
                      Standard Ded: {money(data.comparison.new.standard_deduction)}
                    </small>
                  </div>
                  <div
                    className={
                      data.comparison.recommended_regime === "old"
                        ? "regime selected"
                        : "regime"
                    }
                  >
                    <span>OLD REGIME</span>
                    <b>{money(data.comparison.old.total_tax)}</b>
                    <small>
                      Deductions: {money(data.comparison.old.deductions_claimed)}
                    </small>
                  </div>
                </div>

                {/* Outcome Stats */}
                <div className="outcome-row">
                  <div>
                    <span>
                      {data.result.payable ? "Estimated Tax Due" : "Estimated Refund"}
                    </span>
                    <b>{money(data.result.payable || data.result.refund)}</b>
                  </div>
                  <div>
                    <span>Taxable Ordinary Income</span>
                    <b>{money(data.result.taxable_income)}</b>
                  </div>
                </div>

                <p className="primary-reason">{data.explanation}</p>

                {data.warnings.length > 0 && (
                  <div className="warnings">
                    {data.warnings.map((warning) => (
                      <p key={warning}>! {warning}</p>
                    ))}
                  </div>
                )}

                {/* Interactive Simulator Card */}
                <div className="simulator-card">
                  <span className="eyebrow">WHAT-IF SAVINGS SIMULATOR</span>
                  <h4>Test Potential Adjustments</h4>
                  <div className="sim-slider-row">
                    <label>
                      <span>Add NPS Tier-1: <b>+{money(simNps)}</b></span>
                      <input
                        type="range"
                        min="0"
                        max="50000"
                        step="5000"
                        value={simNps}
                        onChange={(e) => setSimNps(Number(e.target.value))}
                      />
                    </label>
                  </div>
                  <div className="sim-slider-row">
                    <label>
                      <span>Add Parent Health Insurance: <b>+{money(simHealthParents)}</b></span>
                      <input
                        type="range"
                        min="0"
                        max="50000"
                        step="5000"
                        value={simHealthParents}
                        onChange={(e) => setSimHealthParents(Number(e.target.value))}
                      />
                    </label>
                  </div>
                  <button
                    className="sim-btn"
                    onClick={simulateChanges}
                    disabled={simulating}
                  >
                    {simulating ? "Recalculating…" : "Recalculate with Simulated Changes"}
                  </button>
                </div>

                {/* Personalized Opportunities */}
                <div className="reasoning">
                  <div className="reasoning-title">
                    <span className="eyebrow">ACTIONABLE SAVINGS GUIDANCE</span>
                    <h3>Personalized Recommendations</h3>
                  </div>
                  {data.recommendations.length ? (
                    data.recommendations.map((item) => (
                      <article
                        className="opportunity"
                        key={`${item.section}-${item.title}`}
                      >
                        <div className="opportunity-head">
                          <span>{item.section}</span>
                          {item.estimated_tax_saving !== null && (
                            <b>Up to {money(item.estimated_tax_saving)} potential savings</b>
                          )}
                        </div>
                        <h4>{item.title}</h4>
                        {item.potential_deduction !== null && (
                          <p className="deduction">
                            Eligible Capacity: {money(item.potential_deduction)}
                          </p>
                        )}
                        <p>{item.reason}</p>
                        <small>Condition: {item.conditions}</small>
                      </article>
                    ))
                  ) : (
                    <p className="no-opportunities">
                      No additional untapped opportunities found for this profile.
                    </p>
                  )}
                </div>

                {/* Deterministic Trace (Show Why) */}
                <details className="calculation-trace">
                  <summary>
                    <span>Deterministic Calculation & Rule Trace ("Show Why")</span>
                    <span>↓</span>
                  </summary>
                  <div>
                    <p>
                      <b>Gross Income:</b> {money(data.result.gross_income)} |{" "}
                      <b>Deductions:</b> {money(data.result.deductions_claimed)}
                    </p>
                    {Object.entries(data.result.deduction_breakdown).map(([k, v]) => (
                      <p key={k}>
                        • {k}: <b>{money(v)}</b>
                      </p>
                    ))}
                    <hr className="trace-divider" />
                    {data.result.trace.map((step, idx) => (
                      <p key={idx}>[{idx + 1}] {step}</p>
                    ))}
                  </div>
                </details>

                {/* Plain English Q&A Assistant */}
                <div className="qa">
                  <label>
                    Ask the Assistant about this calculation:
                    <input
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                      placeholder="e.g. Why is the new regime better for me?"
                      onKeyDown={(e) => e.key === "Enter" && ask()}
                    />
                  </label>
                  <button onClick={ask} disabled={qaLoading}>
                    {qaLoading ? "Thinking…" : <>Ask <span>→</span></>}
                  </button>
                  {reply && <p className="qa-reply">{reply}</p>}
                </div>
              </>
            )}
          </aside>
        </section>
      )}

      {/* 8 Government Schemes Explorer Tab */}
      {activeTab === "schemes" && (
        <section className="schemes-section">
          <div className="schemes-header">
            <span className="eyebrow">STATUTORY GOVERNMENT SCHEMES</span>
            <h2>8 Canonical Tax-Saving Schemes</h2>
            <p>
              Under Indian Income Tax rules, these 8 primary government schemes allow taxpayers to reduce taxable income when filing under the Old Tax Regime. Every card shows statutory caps, eligibility criteria, and transparent trigger rules.
            </p>
          </div>

          <div className="schemes-grid">
            {(currentSchemes.length > 0
              ? currentSchemes
              : [
                  {
                    scheme_id: "80c",
                    section: "Section 80C",
                    name: "EPF, PPF, ELSS, SSY & Home Loan Principal",
                    category: "Savings & Investments",
                    status: "untapped" as const,
                    claimed_amount: 0,
                    max_limit: 150000,
                    potential_deduction: 150000,
                    estimated_tax_saving: 31200,
                    trigger_rule: "Eligible statutory investment ceiling is ₹1,50,000 per financial year.",
                    plain_explanation: "Allows deductions for EPF, PPF, tax-saving mutual funds (ELSS), Sukanya Samriddhi Yojana (SSY), Life Insurance premiums, and children's school tuition fees.",
                    eligibility_conditions: "Requires maintaining documentary proofs / receipts under the Old Tax Regime.",
                  },
                  {
                    scheme_id: "80ccd_1b",
                    section: "Section 80CCD(1B)",
                    name: "National Pension System (NPS Tier-1)",
                    category: "Retirement Scheme",
                    status: "untapped" as const,
                    claimed_amount: 0,
                    max_limit: 50000,
                    potential_deduction: 50000,
                    estimated_tax_saving: 10400,
                    trigger_rule: "Exclusive ₹50,000 deduction limit over and above the Section 80C cap.",
                    plain_explanation: "Voluntary contributions towards a Tier-1 NPS PRAN account grant an exclusive ₹50k tax shield for long-term retirement savings.",
                    eligibility_conditions: "Applicable only to Tier-1 accounts under Old Tax Regime.",
                  },
                  {
                    scheme_id: "80d",
                    section: "Section 80D",
                    name: "Medical Insurance & Senior Parent Health",
                    category: "Health & Protection",
                    status: "untapped" as const,
                    claimed_amount: 0,
                    max_limit: 75000,
                    potential_deduction: 75000,
                    estimated_tax_saving: 15600,
                    trigger_rule: "Self/Family limit ₹25k (₹50k if senior) + Parent limit ₹25k (₹50k if senior).",
                    plain_explanation: "Deduction for health insurance premiums for self, spouse, children, and parents. Also covers ₹5,000 preventive checkup.",
                    eligibility_conditions: "Premiums must be paid via non-cash banking channels.",
                  },
                  {
                    scheme_id: "24b",
                    section: "Section 24(b)",
                    name: "Home Loan Interest (Self-Occupied)",
                    category: "Housing & Real Estate",
                    status: "untapped" as const,
                    claimed_amount: 0,
                    max_limit: 200000,
                    potential_deduction: 200000,
                    estimated_tax_saving: 41600,
                    trigger_rule: "Up to ₹2,00,000 interest deduction on housing loan taken for acquisition/construction.",
                    plain_explanation: "Reduces taxable income directly by the interest paid on housing loans for self-occupied residential property.",
                    eligibility_conditions: "Construction must be completed within 5 years; bank interest certificate required.",
                  },
                  {
                    scheme_id: "80e",
                    section: "Section 80E",
                    name: "Higher Education Loan Interest",
                    category: "Education & Skilling",
                    status: "not_applicable" as const,
                    claimed_amount: 0,
                    max_limit: null,
                    potential_deduction: 0,
                    estimated_tax_saving: 0,
                    trigger_rule: "100% deduction on interest with no upper statutory ceiling for up to 8 years.",
                    plain_explanation: "Deducts full interest paid on education loans taken for self, spouse, or children for higher studies.",
                    eligibility_conditions: "Loan must be sanctioned by a recognized bank or financial institution.",
                  },
                  {
                    scheme_id: "80tta_ttb",
                    section: "Section 80TTA / 80TTB",
                    name: "Savings & Deposit Interest Exemption",
                    category: "Banking & Savings",
                    status: "untapped" as const,
                    claimed_amount: 0,
                    max_limit: 10000,
                    potential_deduction: 10000,
                    estimated_tax_saving: 2080,
                    trigger_rule: "₹10,000 for regular individuals (80TTA) or ₹50,000 for senior citizens (80TTB).",
                    plain_explanation: "Exempts bank savings interest for individuals, and all deposit interest (including FDs) for senior citizens.",
                    eligibility_conditions: "Old Tax Regime only.",
                  },
                  {
                    scheme_id: "80g",
                    section: "Section 80G",
                    name: "Donations to Approved Relief Funds",
                    category: "Philanthropy",
                    status: "not_applicable" as const,
                    claimed_amount: 0,
                    max_limit: null,
                    potential_deduction: 0,
                    estimated_tax_saving: 0,
                    trigger_rule: "50% or 100% deduction subject to 10% adjusted gross income cap.",
                    plain_explanation: "Tax benefits for donations to authorized charitable trusts, PM Cares / Relief funds.",
                    eligibility_conditions: "Donations above ₹2,000 must be in electronic/banking mode with 10BE receipt.",
                  },
                  {
                    scheme_id: "80ddb",
                    section: "Section 80DDB",
                    name: "Specified Critical Disease Treatment",
                    category: "Medical Support",
                    status: "not_applicable" as const,
                    claimed_amount: 0,
                    max_limit: 40000,
                    potential_deduction: 40000,
                    estimated_tax_saving: 8320,
                    trigger_rule: "₹40,000 limit for general taxpayers; ₹1,00,000 for senior citizens.",
                    plain_explanation: "Deduction for medical expenditure incurred for treatment of specified critical diseases (cancer, renal failure, neurological disorders).",
                    eligibility_conditions: "Prescription certificate (Form 10-I) from a specialist required.",
                  },
                ]
            ).map((scheme) => (
              <div className={`scheme-card ${scheme.status}`} key={scheme.scheme_id}>
                <div className="scheme-card-head">
                  <span className="scheme-section-tag">{scheme.section}</span>
                  <span className={`status-badge ${scheme.status}`}>
                    {scheme.status === "claimed"
                      ? "✓ Fully Claimed"
                      : scheme.status === "partially_claimed"
                      ? "◔ Partially Claimed"
                      : scheme.status === "untapped"
                      ? "⚡ Untapped Potential"
                      : "○ Not Applicable"}
                  </span>
                </div>
                <h3>{scheme.name}</h3>
                <p className="scheme-explanation">{scheme.plain_explanation}</p>
                <div className="scheme-metrics">
                  <div>
                    <span>Statutory Cap</span>
                    <b>{scheme.max_limit ? money(scheme.max_limit) : "No Upper Cap"}</b>
                  </div>
                  <div>
                    <span>Claimed</span>
                    <b>{money(scheme.claimed_amount)}</b>
                  </div>
                  <div>
                    <span>Potential Tax Saving</span>
                    <b className="saving-highlight">
                      {scheme.estimated_tax_saving > 0
                        ? `Up to ${money(scheme.estimated_tax_saving)}`
                        : "₹0"}
                    </b>
                  </div>
                </div>
                <div className="scheme-why-box">
                  <strong>Why it applies:</strong> {scheme.trigger_rule}
                </div>
                <div className="scheme-condition-box">
                  <small>Condition: {scheme.eligibility_conditions}</small>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Rules Config & Slabs Inspector Tab */}
      {activeTab === "rules" && (
        <section className="rules-section">
          <div className="rules-header">
            <span className="eyebrow">EDITABLE STATUTORY RULES ENGINE</span>
            <h2>Transparent Tax Rules & Slabs Configuration</h2>
            <p>
              ConsulTax uses modular, version-controlled JSON rule configurations for statutory rules across financial years.
            </p>
            <div className="year-selector">
              {["2024-25", "2025-26", "2026-27"].map((yr) => (
                <button
                  key={yr}
                  className={`year-btn ${activeRuleYear === yr ? "active" : ""}`}
                  onClick={() => setActiveRuleYear(yr)}
                >
                  FY {yr}
                </button>
              ))}
            </div>
          </div>

          {rulesConfig && rulesConfig[activeRuleYear] ? (
            <div className="rules-display">
              <div className="rule-meta-card">
                <div>
                  <span>Rule Version</span>
                  <b>{rulesConfig[activeRuleYear].version}</b>
                </div>
                <div>
                  <span>Assessment Year</span>
                  <b>{rulesConfig[activeRuleYear].assessment_year}</b>
                </div>
                <div>
                  <span>Standard Deduction (New)</span>
                  <b>{money(rulesConfig[activeRuleYear].new_regime.standard_deduction)}</b>
                </div>
                <div>
                  <span>Section 87A Rebate Limit (New)</span>
                  <b>{money(rulesConfig[activeRuleYear].new_regime.rebate.income_limit)}</b>
                </div>
              </div>

              <div className="slabs-comparison">
                <div className="slabs-column">
                  <h3>New Tax Regime Slabs</h3>
                  <div className="slab-list">
                    {rulesConfig[activeRuleYear].new_regime.slabs.map(
                      (slab: [number | null, number], i: number) => {
                        const prevSlab = i > 0 ? rulesConfig[activeRuleYear].new_regime.slabs[i - 1][0] : 0;
                        const label = slab[0] === null ? `Above ${money(prevSlab)}` : `${money(prevSlab)} – ${money(slab[0])}`;
                        return (
                          <div className="slab-row" key={i}>
                            <span>{label}</span>
                            <b>{(slab[1] * 100).toFixed(0)}%</b>
                          </div>
                        );
                      }
                    )}
                  </div>
                </div>

                <div className="slabs-column">
                  <h3>Old Tax Regime Slabs (Below 60)</h3>
                  <div className="slab-list">
                    {rulesConfig[activeRuleYear].old_regime.slabs_by_age.below_60.map(
                      (slab: [number | null, number], i: number) => {
                        const prevSlab = i > 0 ? rulesConfig[activeRuleYear].old_regime.slabs_by_age.below_60[i - 1][0] : 0;
                        const label = slab[0] === null ? `Above ${money(prevSlab)}` : `${money(prevSlab)} – ${money(slab[0])}`;
                        return (
                          <div className="slab-row" key={i}>
                            <span>{label}</span>
                            <b>{(slab[1] * 100).toFixed(0)}%</b>
                          </div>
                        );
                      }
                    )}
                  </div>
                </div>
              </div>

              <div className="raw-config-box">
                <span className="eyebrow">RAW JSON CONFIGURATION ({activeRuleYear}.json)</span>
                <pre>{JSON.stringify(rulesConfig[activeRuleYear], null, 2)}</pre>
              </div>
            </div>
          ) : (
            <p>Loading rules configuration…</p>
          )}
        </section>
      )}

      {/* Sample Documents & Form 16 Section */}
      {activeTab === "form16" && (
        <section id="form16" className="form16-section">
          <div className="form16-copy">
            <span className="eyebrow">DOCUMENT UNDERSTANDING</span>
            <h2>Clean Sample Documents & Form 16 Parser</h2>
            <p>
              Upload a text-based Form 16 PDF or select from clean structured sample documents to extract gross salary, eligible Chapter VI-A deductions, and TDS credits with plain-English explainers.
            </p>

            <div className="sample-doc-selector">
              <span className="eyebrow">1-CLICK SAMPLE DOCUMENT LOADER:</span>
              <div className="sample-buttons">
                {sampleDocs.map((doc) => (
                  <button
                    key={doc.id}
                    className={`sample-select-btn ${selectedSampleDocId === doc.id ? "active" : ""}`}
                    onClick={() => {
                      setSelectedSampleDocId(doc.id);
                      parseSampleDoc(doc.id);
                    }}
                  >
                    <b>{doc.title}</b>
                    <small>{doc.document_type}</small>
                  </button>
                ))}
              </div>
            </div>

            <div className="privacy-note-card">
              <p>🔒 <strong>Zero Persistence:</strong> Documents are processed in-memory for extraction only and never stored on disk or server databases.</p>
            </div>
          </div>

          <div className="upload-card">
            <input
              ref={uploadRef}
              type="file"
              accept="application/pdf"
              onChange={uploadForm16}
              hidden
            />
            <button
              className="drop-zone"
              onClick={() => uploadRef.current?.click()}
              disabled={uploading}
            >
              <span className="upload-icon">⇧</span>
              <b>{uploading ? "Extracting figures…" : "Upload Form 16 PDF"}</b>
              <small>Text-based PDF · Max 8 MB</small>
            </button>

            {documentError && <p className="error">{documentError}</p>}

            {form16 && (
              <div className="document-result">
                <div className="doc-label">
                  <span>DOCUMENT EXTRACTION RESULT</span>
                  <small>{form16.summary_source}</small>
                </div>
                <p className="doc-summary">{form16.summary}</p>

                {Object.keys(form16.key_figures).length > 0 && (
                  <div className="doc-figures">
                    {Object.entries(form16.key_figures).map(([label, value]) => (
                      <div key={label}>
                        <span>{label}</span>
                        <b>{value}</b>
                      </div>
                    ))}
                  </div>
                )}

                <button
                  className="apply-planner-btn"
                  onClick={applyDocumentToPlanner}
                >
                  Apply Extracted Data to Tax Planner ➔
                </button>

                <details className="doc-explainers">
                  <summary>Plain-Language Explanations of Extracted Terms</summary>
                  <div>
                    {form16.explainers.map((item) => (
                      <p key={item.term}>
                        <b>{item.term}:</b> {item.meaning}
                      </p>
                    ))}
                  </div>
                </details>

                {form16.warnings.map((warning) => (
                  <p className="doc-warning" key={warning}>
                    ! {warning}
                  </p>
                ))}
              </div>
            )}
          </div>
        </section>
      )}

      {/* Footer */}
      <footer>
        <div className="brand">
          Consul<span>Tax</span>
        </div>
        <p>
          AI-Powered Tax Assistant for Filing & Savings Guidance. Built strictly on deterministic statutory rules and plain-English explainability. Indicative guidance only — not a certified tax opinion.
        </p>
        <span>© 2026 ConsulTax · Private Session</span>
      </footer>
    </main>
  );
}

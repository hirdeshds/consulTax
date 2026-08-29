from app.schemas import AnalyzeRequest, ChatRequest, TaxDocument, TaxProfile


def test_schema_contract_exports_and_validates():
    profile = TaxProfile(profile_id="p-1")
    document = TaxDocument(income={"salary": 150000.0})

    analyze = AnalyzeRequest(tax_profile=profile)
    chat = ChatRequest(message="What deductions apply?", tax_profile=profile)

    assert analyze.tax_profile.profile_id == "p-1"
    assert chat.message == "What deductions apply?"
    assert document.income.salary == 150000.0

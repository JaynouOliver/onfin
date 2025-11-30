"""
Configuration for Compliance Agent
Contains: Glossary, Organization Context, and Constants
"""

# =============================================================================
# GLOSSARY - From SEBI (Custodian) Regulations, 1996 - Regulation 2
# =============================================================================

SEBI_GLOSSARY = {
    # Core Terms from Regulation 2
    "Act": "Securities and Exchange Board of India Act, 1992 (15 of 1992)",
    "Board": "Securities and Exchange Board of India (SEBI)",
    "SEBI": "Securities and Exchange Board of India",
    "certificate": "certificate of registration granted by the Board under these regulations",
    
    # Entity Terms
    "client": "any person who has entered into an agreement with a custodian to avail of custodial services",
    "custodian": "any person who carries on or proposes to carry on the business of providing custodial services",
    
    # Service Terms
    "custodial services": "safekeeping of securities or goods or gold or silver and providing services incidental thereto including maintaining accounts, collecting benefits, keeping client informed, and maintaining records",
    "custody account": "an account of a client maintained by a custodian in respect of securities",
    
    # Asset Terms
    "securities": "as defined in clause (h) of section 2 of the Securities Contracts (Regulation) Act, 1956",
    "goods": "goods notified by Central Government under clause (bc) of section 2 of Securities Contracts (Regulation) Act, 1956 forming underlying of commodity derivative contract",
    
    # Document Terms
    "Form": "forms set out in the First Schedule",
    "Schedule": "Schedule annexed to these regulations",
    
    # Officer Terms
    "inspecting officer": "inspecting officer appointed by the Board under regulation 21",
    "compliance officer": "officer responsible for monitoring compliance and redressal of investors grievances",
    
    # Abbreviations
    "AMC": "Asset Management Company",
    "MF": "Mutual Fund",
    "FPI": "Foreign Portfolio Investor",
    "FII": "Foreign Institutional Investor",
    "ETF": "Exchange Traded Fund",
    "AUM": "Assets Under Management",
    "NAV": "Net Asset Value",
    "KYC": "Know Your Customer",
    "AIF": "Alternative Investment Fund",
    "PMS": "Portfolio Management Services",
    
    # Change in Control
    "change in control": "for listed body corporate - as per SEBI takeover regulations; for unlisted - as per Section 2(27) of Companies Act, 2013",
}

# Reverse lookup for normalization
ABBREVIATION_EXPANSIONS = {
    "AMC": "Asset Management Company",
    "MF": "Mutual Fund", 
    "FPI": "Foreign Portfolio Investor",
    "FII": "Foreign Institutional Investor",
    "ETF": "Exchange Traded Fund",
    "SEBI": "Securities and Exchange Board of India",
}


# =============================================================================
# ORGANIZATION CONTEXT - Preloaded for HDFC and Navi AMC
# =============================================================================

HDFC_AMC_CONTEXT = {
    "entity_name": "HDFC Asset Management Company Limited",
    "short_names": ["HDFC AMC", "HDFC Mutual Fund", "HDFC MF"],
    "role_in_custodian_regulations": "Client",
    "entity_type": "Asset Management Company",
    
    # Scheme Information
    "total_schemes": 100,
    "scheme_categories": {
        "equity": 35,
        "debt": 30,
        "hybrid": 15,
        "liquid": 5,
        "gold_etf": 1,
        "silver_etf": 1,
        "fund_of_funds": 8,
        "index_funds": 5,
    },
    
    # Special scheme flags (affects which regulations apply)
    "has_gold_etf": True,
    "has_silver_etf": True,
    "has_commodity_schemes": True,
    "has_real_estate_schemes": False,
    
    # Custodian Relationships
    "custodians": [
        {
            "name": "HDFC Bank Limited",
            "role": "Primary Custodian",
            "services": ["securities", "gold", "silver"]
        },
        {
            "name": "Deutsche Bank AG",
            "role": "Secondary Custodian", 
            "services": ["securities"]
        }
    ],
    "custodian_count": 2,
    
    # Scale Indicators
    "aum_inr_crore": 650000,
    "aum_category": "Large",  # Large > 1 lakh crore
    "investor_count": 10000000,
    
    # Regulatory Status
    "is_listed": True,
    "stock_exchanges": ["NSE", "BSE"],
    "sebi_registration": "MF/HDFC/2000",
    
    # Compliance Implications
    "compliance_factors": {
        "large_amc": True,
        "multiple_custodians": True,
        "commodity_custody": True,
        "listed_entity": True,
        "high_investor_base": True,
    },
    
    # What regulations specifically apply
    "applicable_regulations": {
        "reg_15_gold_silver": True,  # Physical safekeeping delegation
        "reg_16_separate_accounts": True,  # Per scheme
        "reg_17_agreement": True,  # With each custodian
        "reg_17a_dispute_resolution": True,
        "reg_19_records": True,  # Verification rights
        "code_of_conduct": True,  # Verify custodian compliance
    }
}

NAVI_AMC_CONTEXT = {
    "entity_name": "Navi AMC Limited",
    "short_names": ["Navi AMC", "Navi Mutual Fund", "Navi MF"],
    "role_in_custodian_regulations": "Client",
    "entity_type": "Asset Management Company",
    
    # Scheme Information
    "total_schemes": 30,
    "scheme_categories": {
        "equity": 10,
        "debt": 8,
        "hybrid": 5,
        "liquid": 3,
        "index_funds": 4,
    },
    
    # Special scheme flags
    "has_gold_etf": False,
    "has_silver_etf": False,
    "has_commodity_schemes": False,
    "has_real_estate_schemes": False,
    
    # Custodian Relationships
    "custodians": [
        {
            "name": "Axis Bank Limited",
            "role": "Primary Custodian",
            "services": ["securities"]
        }
    ],
    "custodian_count": 1,
    
    # Scale Indicators
    "aum_inr_crore": 15000,
    "aum_category": "Medium",
    "investor_count": 1000000,
    
    # Regulatory Status
    "is_listed": False,
    "stock_exchanges": [],
    "sebi_registration": "MF/NAVI/2021",
    
    # Compliance Implications
    "compliance_factors": {
        "large_amc": False,
        "multiple_custodians": False,
        "commodity_custody": False,
        "listed_entity": False,
        "high_investor_base": False,
    },
    
    # What regulations specifically apply
    "applicable_regulations": {
        "reg_15_gold_silver": False,
        "reg_16_separate_accounts": True,
        "reg_17_agreement": True,
        "reg_17a_dispute_resolution": True,
        "reg_19_records": True,
        "code_of_conduct": True,
    }
}

# Quick lookup
ORG_CONTEXTS = {
    "HDFC AMC": HDFC_AMC_CONTEXT,
    "HDFC": HDFC_AMC_CONTEXT,
    "HDFC Mutual Fund": HDFC_AMC_CONTEXT,
    "Navi AMC": NAVI_AMC_CONTEXT,
    "Navi": NAVI_AMC_CONTEXT,
    "Navi Mutual Fund": NAVI_AMC_CONTEXT,
}


# =============================================================================
# CLAUSE CLASSIFICATION TYPES
# =============================================================================

CLAUSE_TYPES = {
    "definition": "Defines a term (e.g., 'Custodian means...')",
    "internal_ref": "References another part of this document (e.g., 'as per regulation 3...')",
    "external_ref": "References external law/act (e.g., 'as per SEBI Act 1992...')",
    "direct_req": "Standalone compliance requirement (e.g., 'The custodian shall...')",
}


# =============================================================================
# INTERNAL REFERENCE PATTERNS
# =============================================================================

INTERNAL_REF_PATTERNS = [
    r"regulation\s+(\d+[A-Z]?)",
    r"sub-regulation\s*\((\d+)\)",
    r"clause\s*\(([a-z]+)\)",
    r"as per\s+regulation\s+(\d+)",
    r"under\s+regulation\s+(\d+)",
    r"referred to in\s+regulation\s+(\d+)",
    r"specified in\s+regulation\s+(\d+)",
    r"Schedule\s+(I|II|III|First|Second|Third)",
]


# =============================================================================
# EXTERNAL REFERENCE PATTERNS  
# =============================================================================

EXTERNAL_REF_PATTERNS = [
    r"Securities and Exchange Board of India Act",
    r"SEBI Act",
    r"Companies Act",
    r"Securities Contracts? \(Regulation\) Act",
    r"Banking Regulation[s]? Act",
    r"Reserve Bank of India",
    r"RBI",
    r"SEBI \([^)]+\) Regulations",
]


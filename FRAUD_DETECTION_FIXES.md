# 🛡️ Fraud Detection & Document Validation Fixes

## Issues Fixed

### ✅ Issue 1: Layer 3 Explanation Not Displaying
**Problem**: Frontend expected `layer_scores` as `{ layerName: { score, flags } }` but backend returned `{ layerName: 0.5 }`

**Fix**: Updated [aggregator.py](app/ai_agents/fraud/aggregator.py#L12) to return complete layer info:
```python
layer_scores[layer_name] = {
    "score": score,
    "flags": flags,
    "layer": result.get("layer", layer_name),
    "method": result.get("method"),
    "ai_degraded": result.get("ai_degraded", False),
}
```

---

### ✅ Issue 2: All Claims Show Low Risk
**Root Cause**: Document validation results weren't being integrated into Layer 4 fraud scoring

**Fix**: Updated [layer4_document.py](app/ai_agents/fraud/layer4_document.py#L15) to:
- Check `document_validation.validation_status` from context
- Apply high fraud scores (0.75-0.95) for flagged/rejected documents
- Use `fraud_signal_weight` from DocumentGatekeeper

**Example Logic**:
```python
if validation_status == "flagged_critical":
    flags.append(f"DOCUMENT_FLAGGED_CRITICAL:{validation_reason}")
    score = max(score, 0.95)  # Very high fraud score
elif validation_status == "flagged_high_risk":
    flags.append(f"DOCUMENT_FLAGGED_HIGH_RISK:{validation_reason}")
    score = max(score, 0.75)
```

---

### ✅ Issue 3: Document Rejection Not Working
**Problem**: DocumentGatekeeper properly validated documents but fraud engine ignored the results

**Fix**: 
1. **[fraud_service.py](app/services/fraud_service.py#L44)** already passes validation context ✓
2. **[layer4_document.py](app/ai_agents/fraud/layer4_document.py#L15)** now consumes validation status
3. **[orchestrator.py](app/ai_agents/fraud/orchestrator.py#L90)** adds critical override:

```python
if doc_validation.get("validation_status") == "flagged_critical":
    agg["final_score"] = 0.95
    agg["risk_level"] = "VERY_HIGH"
```

---

### ✅ Issue 4: Frontend Type Compatibility
**Fix**: Updated [types/index.ts](frontend/src/types/index.ts#L48) to include `VERY_HIGH` and `MINIMAL` risk levels

---

## How to Test

### Test 1: Invalid Aadhaar Document
```bash
# 1. Upload a document without valid Aadhaar QR signature
# 2. Run fraud analysis
# Expected: HIGH/VERY_HIGH risk with "DOCUMENT_FLAGGED_CRITICAL" flag
```

### Test 2: Valid Documents
```bash
# 1. Upload valid documents (accepted status)
# 2. Run fraud analysis
# Expected: Risk based on other factors (not artificially low)
```

### Test 3: Layer Breakdown Display
```bash
# 1. Run fraud analysis on any claim
# 2. Check fraud tab in UI
# Expected: All 6 layers visible with scores and flags
```

### Test 4: High-Risk Claim Detection
```bash
# Create a claim with:
# - Amount > ₹500,000 (deterministic flag)
# - 3+ claims in 30 days (statistical flag)
# - Invalid document (document flag)
# Expected: HIGH/VERY_HIGH risk with detailed explanation
```

---

## Changes Summary

| File | Changes |
|------|---------|
| [aggregator.py](app/ai_agents/fraud/aggregator.py) | Return full layer info (score + flags) instead of just score |
| [layer4_document.py](app/ai_agents/fraud/layer4_document.py) | Integrate document validation results into fraud scoring |
| [orchestrator.py](app/ai_agents/fraud/orchestrator.py) | Add critical document override logic |
| [fraud.py](app/schemas/fraud.py) | Update schema to `dict[str, Any]` for layer_scores |
| [index.ts](frontend/src/types/index.ts) | Add VERY_HIGH and MINIMAL risk levels |
| [page.tsx](frontend/src/app/claims/[id]/page.tsx) | Handle VERY_HIGH risk level in UI styling |

---

## API Response Structure (After Fix)

```json
{
  "fraud_score": 0.78,
  "risk_level": "HIGH",
  "layer_scores": {
    "deterministic": {
      "score": 0.4,
      "flags": ["AMOUNT_EXCEEDS_TYPE_LIMIT", "HIGH_CLAIM_FREQUENCY_30D"],
      "layer": "deterministic",
      "method": null,
      "ai_degraded": false
    },
    "document": {
      "score": 0.95,
      "flags": ["DOCUMENT_FLAGGED_CRITICAL:Aadhaar QR signature invalid"],
      "layer": "document",
      "method": null,
      "ai_degraded": false
    },
    "narrative": {
      "score": 0.6,
      "flags": ["PRESSURE_PHRASE:'urgent'"],
      "layer": "narrative",
      "method": "gemini_llm",
      "ai_degraded": false
    }
    // ... other layers
  },
  "explanation_text": "High risk due to: 1) Invalid Aadhaar document signature, 2) Claim amount exceeds type limit, 3) Multiple claims filed recently",
  "document_flags": ["DOCUMENT_FLAGGED_CRITICAL:Aadhaar QR signature invalid"]
}
```

---

## What Users Will See

### Before Fix ❌
- Layer scores: blank or just numbers
- All claims: LOW risk (even fraudulent ones)
- Explanation: empty or generic
- Document validation: ignored

### After Fix ✅
- Layer scores: visual bars with expandable flag details
- Proper risk levels: LOW/MEDIUM/HIGH/VERY_HIGH based on actual signals
- Explanation: Gemini-generated reasoning including document issues
- Document validation: properly flags and rejects invalid documents

---

## Verification Checklist

- [x] Aggregator returns complete layer structure
- [x] Layer 4 integrates document validation
- [x] Critical documents override final score
- [x] Frontend displays layer breakdown correctly
- [x] Risk levels include VERY_HIGH and MINIMAL
- [x] All files compile without errors
- [x] Schema updated to match new structure

---

## Next Steps (Optional Enhancements)

1. **Test Coverage**: Add unit tests for new validation logic
2. **Monitoring**: Add alerts for critical document flags
3. **Audit**: Log document validation overrides for compliance
4. **UI Polish**: Add tooltips explaining each flag type
5. **Performance**: Cache DocumentGatekeeper instance per request

---

## Questions?

If fraud detection still shows issues:
1. Check document has `validation_status` field populated
2. Verify DocumentGatekeeper is configured with API keys
3. Check logs for layer execution failures
4. Test each layer individually using context dict

---

Generated: 2026-02-21

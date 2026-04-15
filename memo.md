# Business Questions

## Dataset Summary

This analysis covers **92 customer call extraction files** containing **702 extracted use cases** (471 safety, 231 non-safety). After normalization, these collapse into **198 distinct canonical labels**.

## Quality Findings

Of 702 total use cases, **352** (50.1%) have at least one quality issue.

| Issue Type | Count | % of Total |
|---|---|---|
| cross-bucket-duplicate | 118 | 16.8% |
| vendor-only-evidence | 230 | 32.8% |
| label-inflation | 2 | 0.3% |
| generic-admin | 62 | 8.8% |
| inconsistent-granularity | 27 | 3.8% |

The most prevalent issue is **vendor-only-evidence** (230 rows, 32.8% of the dataset).

## Top 3 Non-Safety Opportunity Recommendations

### 1. Ergonomics risk detection

- **Category:** Ergonomics
- **Mentioned in:** 52 calls
- **Composite score:** 161

**Customer evidence:**

> "Is there a way to, you know, improper bend, also bad, but not really bad, and overreaching, same thing."
> "Kind of talked to them about the incidents and stuff like that and kind of showed them, you know, certain stuff with the improper bending and overreaching, kind of like get their perspective from it and what they think we can do about it."
> "We're currently in the middle of designing for orientation, like a safety class kind of a thing that they're going to go through."

### 2. PPE compliance monitoring

- **Category:** PPE Compliance
- **Mentioned in:** 36 calls
- **Composite score:** 105

**Customer evidence:**

> "I see safety vests there. So the one place that would be applicable for us is on the parking lot. If we have associates out there, we require them to wear a safety vest when they're out there."
> "But how would the camera or the AI distinguish a customer from an associate?"
> "There could be a rare reason where they're back there, and if they are back there, they should have safety yellow on, but..."

### 3. Action tracking and accountability

- **Category:** Compliance & Monitoring
- **Mentioned in:** 22 calls
- **Composite score:** 55

**Customer evidence:**

> "our SOP for the highs are within several hours."
> "So maybe like a few days. Let's do it that way."
> "That helps really track and drive the mitigation part on the back end."

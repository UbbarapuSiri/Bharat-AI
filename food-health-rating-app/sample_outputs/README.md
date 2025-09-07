# Sample Analysis Outputs

Generated: 2025-09-07 16:30:36

## Files in this directory:

### Product Analysis Results
- `product_1.json` - Organic Steel Cut Oats with Flax (Expected: High score)
- `product_2.json` - Whole Wheat Crackers (Expected: Medium score)  
- `product_3.json` - Cheesy Snack Crackers (Expected: Low score)

### Summary Files
- `run_summary.json` - Analysis run statistics and distribution
- `../sources_snapshot.json` - Reference sources with versions and access dates

### Screenshots (to be captured manually)
- `screenshots/main_interface.png` - Main app interface
- `screenshots/analysis_result.png` - Sample analysis result
- `screenshots/evidence_panel.png` - Evidence and sources panel
- `screenshots/history_browser.png` - Product history browser

## Analysis Summary

**Products Analyzed**: 3
**Average Score**: 38.0/100
**Score Distribution**: 
- A Grade: 0 products
- B Grade: 1 products  
- C Grade: 0 products
- D Grade: 1 products
- E Grade: 1 products

## How to Use These Files

1. **Review Analysis Results**: Open any `product_X.json` file to see the complete analysis pipeline from input → normalization → scoring → explanation

2. **Verify Traceability**: Each file contains the full analysis trace showing how raw inputs were transformed into final scores

3. **Check Evidence**: All scoring factors reference authoritative sources listed in `sources_snapshot.json`

4. **Reproduce Results**: Use the barcode from any product file to look up the same analysis in the app

## Next Steps

1. Run the Streamlit app: `streamlit run app.py`
2. Use "Barcode Lookup" with any of the sample barcodes
3. Verify that cached results match these JSON files
4. Capture screenshots for documentation

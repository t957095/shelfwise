# ShelfWise POS Import Demo Report

Generated: 2026-06-13 16:51:11

## Summary
- Total SKUs imported: 19
- Fully enriched: 18
- Partially enriched: 1
- Failed / unknown: 0
- Azure Foundry LLM enriched: 19
- Success rate: 100.0%

## Enrichment Highlights

Products enriched by Microsoft Azure Foundry LLM (cross-referencing beyond scraper data):

### Coca-Cola Original Taste (UPC: 049000050103)
- **Department**: Beverages
- **Status**: complete
- **Confidence**: 1.00
- **Brand**: Coca-Cola
- **Category**: Colas
- **Description**: Coca-Cola Original Taste is a refreshing carbonated soft drink with a classic flavor enjoyed worldwide. Perfect for any occasion, it delivers a crisp and satisfying taste.
- **Reasoning trace**:
  - Starting consolidation for UPC 049000050103
  - Weighted 2 sources: Open Food Facts(0.90), UPCItemDB(0.85)
  - Resolved name: 'Coca Cola' from ['Open Food Facts']
  - Resolved brand: 'Coca-Cola, Coca-Cola Original Taste' from ['Open Food Facts']
  - Resolved category: 'Colas' from ['Open Food Facts']
  - Merged 11 attributes from all sources
  - Generated description (235 chars)
  - Selected 9 images, best: True
  - Computed confidence: 1.00
  - Generated 2 citations
  - Status: complete
  - Microsoft Foundry reasoning applied
  - Foundry enriched fields merged — full product data from LLM
- **Sources**:
  - Open Food Facts (confidence: 0.90)
  - UPCItemDB (confidence: 0.85)

### Pepsi Light (UPC: 012000001307)
- **Department**: Beverages
- **Status**: complete
- **Confidence**: 1.00
- **Brand**: Pepsi
- **Category**: Food, Beverages & Tobacco > Beverages > Soda
- **Description**: Pepsi Light is a refreshing, zero-calorie soda from Pepsi, offering the classic cola taste without the sugar.
- **Reasoning trace**:
  - Starting consolidation for UPC 012000001307
  - Weighted 2 sources: Open Food Facts(0.90), UPCItemDB(0.85)
  - Resolved name: 'Pepsi Light' from ['Open Food Facts']
  - Resolved brand: 'Pepsi' from ['Open Food Facts']
  - Resolved category: 'Food, Beverages & Tobacco > Beverages > Soda' from ['UPCItemDB']
  - Merged 6 attributes from all sources
  - Generated description (175 chars)
  - Selected 9 images, best: True
  - Computed confidence: 1.00
  - Generated 2 citations
  - Status: complete
  - Microsoft Foundry reasoning applied
  - Foundry enriched fields merged — full product data from LLM
- **Sources**:
  - Open Food Facts (confidence: 0.90)
  - UPCItemDB (confidence: 0.85)

### Coca-Cola Classic Soda (UPC: 049000012781)
- **Department**: Beverages
- **Status**: complete
- **Confidence**: 1.00
- **Brand**: Coca-Cola
- **Category**: Soft Drinks
- **Description**: Coca-Cola Classic Soda is a refreshing, carbonated beverage with a signature taste enjoyed worldwide. Packaged in a convenient 24-pack of 12 fl oz cans, perfect for sharing or stocking up.
- **Reasoning trace**:
  - Starting consolidation for UPC 049000012781
  - Weighted 1 sources: Open Food Facts(0.90)
  - Resolved name: 'Coca-Cola' from ['Open Food Facts']
  - Resolved brand: 'Coca-Cola' from ['Open Food Facts']
  - Resolved category: 'None' from []
  - Merged 3 attributes from all sources
  - Generated description (152 chars)
  - Selected 1 images, best: True
  - Computed confidence: 0.80
  - Generated 1 citations
  - Status: complete
  - Microsoft Foundry reasoning applied
  - Foundry enriched fields merged — full product data from LLM
- **Sources**:
  - Open Food Facts (confidence: 0.90)

### Coca-Cola Classic (UPC: 049000000443)
- **Department**: Beverages
- **Status**: complete
- **Confidence**: 1.00
- **Brand**: Coca-Cola
- **Category**: Soft Drinks
- **Description**: Coca-Cola Classic is a refreshing, carbonated cola beverage with a signature taste enjoyed worldwide. Perfect for any occasion, it delivers a burst of flavor with every sip.
- **Reasoning trace**:
  - Starting consolidation for UPC 049000000443
  - Weighted 1 sources: Open Food Facts(0.90)
  - Resolved name: 'Coca-Cola' from ['Open Food Facts']
  - Resolved brand: 'Coca-Cola' from ['Open Food Facts']
  - Resolved category: 'Colas' from ['Open Food Facts']
  - Merged 3 attributes from all sources
  - Generated description (184 chars)
  - Selected 3 images, best: True
  - Computed confidence: 0.85
  - Generated 1 citations
  - Status: complete
  - Microsoft Foundry reasoning applied
  - Foundry enriched fields merged — full product data from LLM
- **Sources**:
  - Open Food Facts (confidence: 0.90)

### Lay's Classic Potato Crisps (UPC: 028400199148)
- **Department**: Snacks
- **Status**: complete
- **Confidence**: 1.00
- **Brand**: Lay's
- **Category**: Potato Crisps
- **Description**: Lay's Classic Potato Crisps are made from fresh potatoes, cooked to perfection, and lightly seasoned with salt for a timeless, satisfying crunch.
- **Reasoning trace**:
  - Starting consolidation for UPC 028400199148
  - Weighted 1 sources: Open Food Facts(0.90)
  - Resolved name: 'Classic' from ['Open Food Facts']
  - Resolved brand: 'Lay's' from ['Open Food Facts']
  - Resolved category: 'Potato crisps' from ['Open Food Facts']
  - Merged 4 attributes from all sources
  - Generated description (222 chars)
  - Selected 3 images, best: True
  - Computed confidence: 0.85
  - Generated 1 citations
  - Status: complete
  - Microsoft Foundry reasoning applied
  - Foundry enriched fields merged — full product data from LLM
- **Sources**:
  - Open Food Facts (confidence: 0.90)

### Unknown Product (UPC: 28400357012)
- **Department**: Snacks
- **Status**: complete
- **Confidence**: 0.25
- **Brand**: unknown
- **Category**: unknown
- **Description**: Unknown Product
- **Reasoning trace**:
  - Starting consolidation for UPC 28400357012
  - No scraper data found — will attempt Foundry LLM enrichment from UPC alone
  - Weighted 0 sources: 
  - Resolved name: 'Unknown Product' from []
  - Resolved brand: 'None' from []
  - Resolved category: 'None' from []
  - Merged 0 attributes from all sources
  - Generated description (15 chars)
  - Selected 0 images, best: False
  - Computed confidence: 0.00
  - Generated 0 citations
  - Status: error
  - Microsoft Foundry reasoning applied
  - Status promoted from error to complete by Foundry LLM
  - Foundry enriched fields merged — full product data from LLM

### M&M's Milk Chocolate Candies (UPC: 022000020806)
- **Department**: Candy
- **Status**: partial
- **Confidence**: 0.30
- **Brand**: Mars
- **Category**: Candy & Chocolate
- **Description**: M&M's Milk Chocolate Candies are colorful, candy-coated chocolates in a convenient 1.69 oz bag, perfect for snacking or sharing.
- **Reasoning trace**:
  - Starting consolidation for UPC 022000020806
  - Weighted 1 sources: Demo Fallback(0.40)
  - Resolved name: 'M&M's Milk Chocolate' from ['Demo Fallback']
  - Resolved brand: 'Mars' from ['Demo Fallback']
  - Resolved category: 'Candy & Chocolate' from ['Demo Fallback']
  - Merged 3 attributes from all sources
  - Generated description (112 chars)
  - Selected 0 images, best: False
  - Computed confidence: 0.05
  - Generated 1 citations
  - Status: partial
  - Microsoft Foundry reasoning applied
  - Foundry enriched fields merged — full product data from LLM
- **Sources**:
  - Demo Fallback (confidence: 0.40)

### Unknown Product (UPC: 038000131212)
- **Department**: Breakfast
- **Status**: complete
- **Confidence**: 0.25
- **Brand**: unknown
- **Category**: unknown
- **Description**: Unknown Product
- **Reasoning trace**:
  - Starting consolidation for UPC 038000131212
  - No scraper data found — will attempt Foundry LLM enrichment from UPC alone
  - Weighted 0 sources: 
  - Resolved name: 'Unknown Product' from []
  - Resolved brand: 'None' from []
  - Resolved category: 'None' from []
  - Merged 0 attributes from all sources
  - Generated description (15 chars)
  - Selected 0 images, best: False
  - Computed confidence: 0.00
  - Generated 0 citations
  - Status: error
  - Microsoft Foundry reasoning applied
  - Status promoted from error to complete by Foundry LLM
  - Foundry enriched fields merged — full product data from LLM

### Unknown Product (UPC: 016000131214)
- **Department**: Breakfast
- **Status**: complete
- **Confidence**: 0.25
- **Brand**: unknown
- **Category**: unknown
- **Description**: Unknown Product
- **Reasoning trace**:
  - Starting consolidation for UPC 016000131214
  - No scraper data found — will attempt Foundry LLM enrichment from UPC alone
  - Weighted 0 sources: 
  - Resolved name: 'Unknown Product' from []
  - Resolved brand: 'None' from []
  - Resolved category: 'None' from []
  - Merged 0 attributes from all sources
  - Generated description (15 chars)
  - Selected 0 images, best: False
  - Computed confidence: 0.00
  - Generated 0 citations
  - Status: error
  - Microsoft Foundry reasoning applied
  - Status promoted from error to complete by Foundry LLM
  - Foundry enriched fields merged — full product data from LLM

### Unknown Product (UPC: 0360000563000)
- **Department**: Cookies
- **Status**: complete
- **Confidence**: 0.25
- **Brand**: unknown
- **Category**: unknown
- **Description**: Unknown Product
- **Reasoning trace**:
  - Starting consolidation for UPC 0360000563000
  - No scraper data found — will attempt Foundry LLM enrichment from UPC alone
  - Weighted 0 sources: 
  - Resolved name: 'Unknown Product' from []
  - Resolved brand: 'None' from []
  - Resolved category: 'None' from []
  - Merged 0 attributes from all sources
  - Generated description (15 chars)
  - Selected 0 images, best: False
  - Computed confidence: 0.00
  - Generated 0 citations
  - Status: error
  - Microsoft Foundry reasoning applied
  - Status promoted from error to complete by Foundry LLM
  - Foundry enriched fields merged — full product data from LLM

### Unknown Product (UPC: 064200001000)
- **Department**: Condiments
- **Status**: complete
- **Confidence**: 0.25
- **Brand**: unknown
- **Category**: unknown
- **Description**: Unknown Product
- **Reasoning trace**:
  - Starting consolidation for UPC 064200001000
  - No scraper data found — will attempt Foundry LLM enrichment from UPC alone
  - Weighted 0 sources: 
  - Resolved name: 'Unknown Product' from []
  - Resolved brand: 'None' from []
  - Resolved category: 'None' from []
  - Merged 0 attributes from all sources
  - Generated description (15 chars)
  - Selected 0 images, best: False
  - Computed confidence: 0.00
  - Generated 0 citations
  - Status: error
  - Microsoft Foundry reasoning applied
  - Status promoted from error to complete by Foundry LLM
  - Foundry enriched fields merged — full product data from LLM

### Unknown Product (UPC: 007874200000)
- **Department**: Dairy
- **Status**: complete
- **Confidence**: 0.25
- **Brand**: unknown
- **Category**: unknown
- **Description**: Unknown Product
- **Reasoning trace**:
  - Starting consolidation for UPC 007874200000
  - No scraper data found — will attempt Foundry LLM enrichment from UPC alone
  - Weighted 0 sources: 
  - Resolved name: 'Unknown Product' from []
  - Resolved brand: 'None' from []
  - Resolved category: 'None' from []
  - Merged 0 attributes from all sources
  - Generated description (15 chars)
  - Selected 0 images, best: False
  - Computed confidence: 0.00
  - Generated 0 citations
  - Status: error
  - Microsoft Foundry reasoning applied
  - Status promoted from error to complete by Foundry LLM
  - Foundry enriched fields merged — full product data from LLM

### Unknown Product (UPC: 037000010000)
- **Department**: Household
- **Status**: complete
- **Confidence**: 0.25
- **Brand**: unknown
- **Category**: unknown
- **Description**: Unknown Product
- **Reasoning trace**:
  - Starting consolidation for UPC 037000010000
  - No scraper data found — will attempt Foundry LLM enrichment from UPC alone
  - Weighted 0 sources: 
  - Resolved name: 'Unknown Product' from []
  - Resolved brand: 'None' from []
  - Resolved category: 'None' from []
  - Merged 0 attributes from all sources
  - Generated description (15 chars)
  - Selected 0 images, best: False
  - Computed confidence: 0.00
  - Generated 0 citations
  - Status: error
  - Microsoft Foundry reasoning applied
  - Status promoted from error to complete by Foundry LLM
  - Foundry enriched fields merged — full product data from LLM

### Unknown Product (UPC: 001901821007)
- **Department**: Electronics
- **Status**: complete
- **Confidence**: 0.25
- **Brand**: unknown
- **Category**: unknown
- **Description**: Unknown Product
- **Reasoning trace**:
  - Starting consolidation for UPC 001901821007
  - No scraper data found — will attempt Foundry LLM enrichment from UPC alone
  - Weighted 0 sources: 
  - Resolved name: 'Unknown Product' from []
  - Resolved brand: 'None' from []
  - Resolved category: 'None' from []
  - Merged 0 attributes from all sources
  - Generated description (15 chars)
  - Selected 0 images, best: False
  - Computed confidence: 0.00
  - Generated 0 citations
  - Status: error
  - Microsoft Foundry reasoning applied
  - Status promoted from error to complete by Foundry LLM
  - Foundry enriched fields merged — full product data from LLM

### Unknown Product (UPC: 007164100000)
- **Department**: Office
- **Status**: complete
- **Confidence**: 0.25
- **Brand**: unknown
- **Category**: unknown
- **Description**: Unknown Product
- **Reasoning trace**:
  - Starting consolidation for UPC 007164100000
  - No scraper data found — will attempt Foundry LLM enrichment from UPC alone
  - Weighted 0 sources: 
  - Resolved name: 'Unknown Product' from []
  - Resolved brand: 'None' from []
  - Resolved category: 'None' from []
  - Merged 0 attributes from all sources
  - Generated description (15 chars)
  - Selected 0 images, best: False
  - Computed confidence: 0.00
  - Generated 0 citations
  - Status: error
  - Microsoft Foundry reasoning applied
  - Status promoted from error to complete by Foundry LLM
  - Foundry enriched fields merged — full product data from LLM

### Unknown Product (UPC: 003165400000)
- **Department**: Health
- **Status**: complete
- **Confidence**: 0.25
- **Brand**: unknown
- **Category**: unknown
- **Description**: Unknown Product
- **Reasoning trace**:
  - Starting consolidation for UPC 003165400000
  - No scraper data found — will attempt Foundry LLM enrichment from UPC alone
  - Weighted 0 sources: 
  - Resolved name: 'Unknown Product' from []
  - Resolved brand: 'None' from []
  - Resolved category: 'None' from []
  - Merged 0 attributes from all sources
  - Generated description (15 chars)
  - Selected 0 images, best: False
  - Computed confidence: 0.00
  - Generated 0 citations
  - Status: error
  - Microsoft Foundry reasoning applied
  - Status promoted from error to complete by Foundry LLM
  - Foundry enriched fields merged — full product data from LLM

### Unknown Product (UPC: 017800011000)
- **Department**: Pet Care
- **Status**: complete
- **Confidence**: 0.25
- **Brand**: unknown
- **Category**: unknown
- **Description**: Unknown Product
- **Reasoning trace**:
  - Starting consolidation for UPC 017800011000
  - No scraper data found — will attempt Foundry LLM enrichment from UPC alone
  - Weighted 0 sources: 
  - Resolved name: 'Unknown Product' from []
  - Resolved brand: 'None' from []
  - Resolved category: 'None' from []
  - Merged 0 attributes from all sources
  - Generated description (15 chars)
  - Selected 0 images, best: False
  - Computed confidence: 0.00
  - Generated 0 citations
  - Status: error
  - Microsoft Foundry reasoning applied
  - Status promoted from error to complete by Foundry LLM
  - Foundry enriched fields merged — full product data from LLM

### Unknown Product (UPC: 007000010000)
- **Department**: Frozen
- **Status**: complete
- **Confidence**: 0.25
- **Brand**: unknown
- **Category**: unknown
- **Description**: Unknown Product
- **Reasoning trace**:
  - Starting consolidation for UPC 007000010000
  - No scraper data found — will attempt Foundry LLM enrichment from UPC alone
  - Weighted 0 sources: 
  - Resolved name: 'Unknown Product' from []
  - Resolved brand: 'None' from []
  - Resolved category: 'None' from []
  - Merged 0 attributes from all sources
  - Generated description (15 chars)
  - Selected 0 images, best: False
  - Computed confidence: 0.00
  - Generated 0 citations
  - Status: error
  - Microsoft Foundry reasoning applied
  - Status promoted from error to complete by Foundry LLM
  - Foundry enriched fields merged — full product data from LLM

### Unknown Product (UPC: 037000100000)
- **Department**: Personal Care
- **Status**: complete
- **Confidence**: 0.25
- **Brand**: unknown
- **Category**: unknown
- **Description**: Unknown Product
- **Reasoning trace**:
  - Starting consolidation for UPC 037000100000
  - No scraper data found — will attempt Foundry LLM enrichment from UPC alone
  - Weighted 0 sources: 
  - Resolved name: 'Unknown Product' from []
  - Resolved brand: 'None' from []
  - Resolved category: 'None' from []
  - Merged 0 attributes from all sources
  - Generated description (15 chars)
  - Selected 0 images, best: False
  - Computed confidence: 0.00
  - Generated 0 citations
  - Status: error
  - Microsoft Foundry reasoning applied
  - Status promoted from error to complete by Foundry LLM
  - Foundry enriched fields merged — full product data from LLM

## Raw Data Comparison

Before vs after enrichment — showing how Foundry LLM resolves conflicts and fills gaps:

### UPC 049000050103
- POS input: Beverages, Qty 24
- Enriched name: Coca-Cola Original Taste
- Enriched brand: Coca-Cola
- Enriched category: Colas
- Final status: complete

### UPC 012000001307
- POS input: Beverages, Qty 18
- Enriched name: Pepsi Light
- Enriched brand: Pepsi
- Enriched category: Food, Beverages & Tobacco > Beverages > Soda
- Final status: complete

### UPC 049000012781
- POS input: Beverages, Qty 12
- Enriched name: Coca-Cola Classic Soda
- Enriched brand: Coca-Cola
- Enriched category: Soft Drinks
- Final status: complete

### UPC 049000000443
- POS input: Beverages, Qty 48
- Enriched name: Coca-Cola Classic
- Enriched brand: Coca-Cola
- Enriched category: Soft Drinks
- Final status: complete

### UPC 028400199148
- POS input: Snacks, Qty 36
- Enriched name: Lay's Classic Potato Crisps
- Enriched brand: Lay's
- Enriched category: Potato Crisps
- Final status: complete

### UPC 28400357012
- POS input: Snacks, Qty 24
- Enriched name: Unknown Product
- Enriched brand: unknown
- Enriched category: unknown
- Final status: complete

### UPC 022000020806
- POS input: Candy, Qty 20
- Enriched name: M&M's Milk Chocolate Candies
- Enriched brand: Mars
- Enriched category: Candy & Chocolate
- Final status: partial

### UPC 038000131212
- POS input: Breakfast, Qty 15
- Enriched name: Unknown Product
- Enriched brand: unknown
- Enriched category: unknown
- Final status: complete

### UPC 016000131214
- POS input: Breakfast, Qty 20
- Enriched name: Unknown Product
- Enriched brand: unknown
- Enriched category: unknown
- Final status: complete

### UPC 0360000563000
- POS input: Cookies, Qty 30
- Enriched name: Unknown Product
- Enriched brand: unknown
- Enriched category: unknown
- Final status: complete

### UPC 064200001000
- POS input: Condiments, Qty 18
- Enriched name: Unknown Product
- Enriched brand: unknown
- Enriched category: unknown
- Final status: complete

### UPC 007874200000
- POS input: Dairy, Qty 25
- Enriched name: Unknown Product
- Enriched brand: unknown
- Enriched category: unknown
- Final status: complete

### UPC 037000010000
- POS input: Household, Qty 12
- Enriched name: Unknown Product
- Enriched brand: unknown
- Enriched category: unknown
- Final status: complete

### UPC 001901821007
- POS input: Electronics, Qty 40
- Enriched name: Unknown Product
- Enriched brand: unknown
- Enriched category: unknown
- Final status: complete

### UPC 007164100000
- POS input: Office, Qty 50
- Enriched name: Unknown Product
- Enriched brand: unknown
- Enriched category: unknown
- Final status: complete

### UPC 003165400000
- POS input: Health, Qty 15
- Enriched name: Unknown Product
- Enriched brand: unknown
- Enriched category: unknown
- Final status: complete

### UPC 017800011000
- POS input: Pet Care, Qty 20
- Enriched name: Unknown Product
- Enriched brand: unknown
- Enriched category: unknown
- Final status: complete

### UPC 007000010000
- POS input: Frozen, Qty 10
- Enriched name: Unknown Product
- Enriched brand: unknown
- Enriched category: unknown
- Final status: complete

### UPC 037000100000
- POS input: Personal Care, Qty 15
- Enriched name: Unknown Product
- Enriched brand: unknown
- Enriched category: unknown
- Final status: complete
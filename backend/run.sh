#   cd backend                                                                                                                                                                                
uvicorn app.main:app --reload --port 8000
#   pytest tests/ -q                                                                                                                                                                          
#   python tests/eval/run_eval.py                                   

#    kill all uvicorn instances
# pkill -f uvicorn


# inside backend/ directory
# python tests/eval/run_eval.py

#   1. Unit tests (no running server needed)                        
                                                                                                                                                                                            
#   cd backend                                                      
#   pytest tests/ -q                                                                                                                                                                          
                                                                  
#   Tests all existing RAG, ETL, route, and integration logic. All 122 tests pass. The new metrics modules have no side effects so they are covered by the import smoke-test that happens as  
#   part of collection.   

# 2. End-to-end eval harness (requires the API server to be running)
                                                                                                                                                                                            
#   Standard run — all metrics, all modes:
#   cd backend                                                                                                                                                                                
#   python tests/eval/run_eval.py                                   
                                                                                                                                                                                            
#   With LLM-based metrics (answer_relevance, context_recall, context_precision in Mode 3):
#   export OPENAI_API_KEY=sk-...                                                                                                                                                              
#   python tests/eval/run_eval.py                                   
                                                                                                                                                                                            
#   With robustness metrics (query_consistency + noise_sensitivity, Mode 2 only):                                                                                                             
#   export OPENAI_API_KEY=sk-...
#   python tests/eval/run_eval.py --robustness                                                                                                                                                
                                                                  
#   Quick smoke-test — Mode 2 only, skip re-ingestion:                                                                                                                                        
#   python tests/eval/run_eval.py --modes 2 --skip-ingest                                                                                                                                     
   
#   Custom output dir:                                                                                                                                                                        
#   python tests/eval/run_eval.py --output-dir /tmp/eval_results    


#   │     Flag combo      │                                                            Metrics exercised                                                            │                         
#   ├─────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
#   │ No OPENAI_API_KEY   │ completeness, hallucination_rate, citation_accuracy/coverage, context_precision (GT path in Mode 2), all binary hits, IR, latency, cost │                         
#   ├─────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
#   │ With OPENAI_API_KEY │ All of the above + answer_relevance[llm], context_recall[llm], context_precision[llm] (Modes 1/3), faithfulness[llm]                    │                         
#   ├─────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤                         
#   │ --robustness        │ Adds query_consistency + noise_sensitivity for each Mode 2 question                                                                     │                         
#   └─────────────────────┴────────────────────────────────────────────────────────────────────────
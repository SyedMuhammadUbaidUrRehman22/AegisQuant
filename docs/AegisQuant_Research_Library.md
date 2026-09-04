# AegisQuant Research Library

> **Purpose:** Clean research/resource index derived from the 46-entry bibliography in `aegisquant_literature_review.pdf`, with direct web links where the cited work could be identified.
>
> **Important:** The source literature review mixes peer-reviewed papers, working papers/preprints, books, technical articles, and practitioner resources. This library preserves all **46 source entries** rather than silently dropping non-academic material. Where the source citation is incomplete or ambiguous, that is explicitly marked.

## Classification

- **[PAPER]** Research paper / journal or conference publication
- **[PREPRINT]** arXiv/SSRN/working paper
- **[BOOK]** Academic book
- **[ARTICLE]** Technical/practitioner/educational article
- **[RESOURCE]** Web resource
- **[UNVERIFIED]** Source citation in the literature review is too incomplete to uniquely identify a canonical publication

---

## 1. Market Regime Detection & HMMs

### 01. Hamilton — A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle
**Type:** [PAPER]  
**Author:** James D. Hamilton  
**Year:** 1989  
**Venue:** *Econometrica*, 57(2), 357–384  
**Relevance:** Foundational Markov-switching/regime-detection methodology.

- DOI / publisher: https://doi.org/10.2307/1912559
- JSTOR: https://www.jstor.org/stable/1912559

### 02. Market Regime Detection via Realized Covariances
**Type:** [PAPER]  
**Authors:** Andrea Bucci, Vito Ciciretti  
**Year:** 2022  
**Venue:** *Economic Modelling*, 111, 105832  
**Relevance:** Uses realized covariance information to identify market regimes and volatile transitions.

- ScienceDirect: https://www.sciencedirect.com/science/article/pii/S0264999322000785
- arXiv: https://arxiv.org/abs/2104.03667

### 03. Tactical Asset Allocation with Macroeconomic Regime Detection
**Type:** [PAPER/PREPRINT]  
**Authors:** Daniel Cunha Oliveira, Dylan Sandfelder, André Fujita, Xiaowen Dong, Mihai Cucuringu  
**Year:** 2025/2026  
**Venue:** *Quantitative Finance*  
**Relevance:** Macro-regime detection integrated with tactical asset allocation.

- Publisher: https://www.tandfonline.com/doi/full/10.1080/14697688.2026.2659195
- arXiv: https://arxiv.org/abs/2503.11499

### 04. Hidden Markov Models in Finance: Further Developments and Applications, Volume II
**Type:** [BOOK]  
**Editors:** R. S. Mamon, R. J. Elliott  
**Year:** 2014  
**Publisher:** Springer  
**Relevance:** Broad reference on HMM applications in finance.

- Springer: https://link.springer.com/book/10.1007/978-1-4899-7442-6

### 05. Parameter Estimation in a Regime-Switching Model with Non-normal Noise
**Type:** [BOOK CHAPTER]  
**Authors:** Luka Jalen, Rogemar S. Mamon  
**Year:** 2014  
**In:** *Hidden Markov Models in Finance*, pp. 241–261  
**Relevance:** Regime-switching parameter estimation under non-normal noise.

- Springer: https://link.springer.com/chapter/10.1007/978-1-4899-7442-6_11
- DOI: https://doi.org/10.1007/978-1-4899-7442-6_11

### 06. Adaptive Regime-Aware Stock Price Prediction Using Autoencoder-Gated Dual Node Transformers with Reinforcement Learning Control
**Type:** [PREPRINT]  
**Year:** 2026  
**Relevance:** Combines autoencoders, Transformer architecture and reinforcement learning for regime-aware prediction.

- arXiv: https://arxiv.org/abs/2603.19136

---

## 2. Deep Learning & Representation Learning

### 07. Deep Learning for Financial Time Series Prediction: A State-of-the-Art Survey
**Type:** [PAPER/REVIEW]  
**Relevance:** Broad review of deep learning methods for financial time-series prediction.

- ScienceDirect: https://www.sciencedirect.com/org/science/article/pii/S152614922300125X

### 08. LSTM–Transformer-Based Robust Hybrid Deep Learning Model for Financial Time Series Forecasting
**Type:** [PAPER]  
**Year:** 2025  
**Venue:** *Data* (MDPI)  
**Relevance:** Hybrid LSTM/Transformer architecture for financial forecasting.

- MDPI: https://www.mdpi.com/2413-4155/7/1/7

### 09. Deep Learning for Financial Time Series: A Large-Scale Benchmark of Risk-Adjusted Performance
**Type:** [PREPRINT]  
**Authors:** Adir Saly-Kaufmann, Kieran Wood, Jan Peter-Calliess, Stefan Zohren  
**Year:** 2026  
**arXiv:** 2603.01820  
**Relevance:** Large-scale benchmark of deep-learning architectures, including xLSTM variants, with financially relevant evaluation.

- arXiv: https://arxiv.org/abs/2603.01820

### 10. Research on Financial Time Series Prediction Based on LSTM and Attention Mechanism
**Type:** [PAPER — SOURCE CITATION INCOMPLETE]  
**Relevance:** LSTM forecasting augmented with attention mechanisms.

- IEEE Xplore search: https://ieeexplore.ieee.org/search/searchresult.jsp?newsearch=true&queryText=Research%20on%20Financial%20Time%20Series%20Prediction%20Based%20on%20LSTM%20and%20Attention%20Mechanism
- **Verification note:** The literature review does not provide authors, year, DOI or article number, so this entry should be bibliographically verified before academic citation.

### 11. Attention Mechanism in Financial Forecasting
**Type:** [ARTICLE]  
**Relevance:** Practitioner/educational explanation of attention mechanisms in financial forecasting.  
**Note:** Not treated as peer-reviewed research.

- Meegle: https://www.meegle.com/en_us/topics/attention-mechanism/attention-mechanism-in-financial-forecasting

### 12. Representation Learning for Financial Time Series Forecasting
**Type:** [PAPER/PREPRINT]  
**Authors:** Antony Krymski, Paul Alexander Bilokon, Tom Davison  
**Year:** 2024  
**Relevance:** Contrastive Predictive Coding and learned representations for financial time-series forecasting.

- SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4950195

### 13. Contrastive Learning of Asset Embeddings from Financial Time Series
**Type:** [PAPER]  
**Authors:** Rian Dolphin, Barry Smyth, Ruihai Dong  
**Year:** 2024  
**Venue:** ICAIF 2024  
**Relevance:** Contrastive asset embeddings for discovering relationships among financial assets.

- arXiv: https://arxiv.org/abs/2407.18645
- DOI: https://doi.org/10.1145/3677052.3698610

### 14. Fin-JEPA: Joint-Embedding Predictive Representation Learning for Financial Time Series
**Type:** [PREPRINT]  
**Author:** Yihan Wang  
**Year:** 2026  
**Relevance:** JEPA-style self-supervised representation learning for daily equity time series.

- SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6855118
- DOI: https://doi.org/10.2139/ssrn.6855118

---

## 3. Portfolio Optimization & Convex Optimization

### 15. Portfolio Selection
**Type:** [PAPER]  
**Author:** Harry Markowitz  
**Year:** 1952  
**Venue:** *The Journal of Finance*, 7(1), 77–91  
**Relevance:** Foundation of Modern Portfolio Theory and mean-variance optimization.

- DOI: https://doi.org/10.1111/j.1540-6261.1952.tb01525.x

### 16. Advancements in Modern Portfolio Theory
**Type:** [ARTICLE]  
**Publisher:** Ortec Finance  
**Relevance:** Overview of developments in portfolio theory beyond the original Markowitz framework.  
**Note:** Practitioner article, not a peer-reviewed paper.

- Ortec Finance: https://www.ortecfinance.com/en/insights/blog/advancements-in-modern-portfolio-theory

### 17. Multi-Period Trading via Convex Optimization
**Type:** [PAPER/MONOGRAPH]  
**Authors:** Stephen Boyd, Enzo Busseti, Steven Diamond, Ronald Kahn, Kwangmoo Koh, Peter Nystrup, Jan Speth  
**Year:** 2017  
**Relevance:** Convex optimization for multi-period portfolio/trading problems, including transaction costs and constraints.

- Stanford: https://stanford.edu/~boyd/papers/cvx_portfolio.html

### 18. Convex Optimization
**Type:** [BOOK]  
**Authors:** Stephen Boyd, Lieven Vandenberghe  
**Year:** 2004  
**Publisher:** Cambridge University Press  
**Relevance:** Core mathematical reference for convex optimization.

- Official book site: https://www.seas.ucla.edu/~vandenbe/cvxbook.html

### 19. CVXPY: A Python-Embedded Modeling Language for Convex Optimization
**Type:** [PAPER]  
**Authors:** Steven Diamond, Stephen Boyd  
**Year:** 2016  
**Venue:** *Journal of Machine Learning Research*, 17(83), 1–5?  
**Relevance:** Canonical paper for CVXPY, the optimization modeling layer used by AegisQuant.

- JMLR: https://www.jmlr.org/papers/v17/15-408.html
- arXiv: https://arxiv.org/abs/1603.00943
- DOI: https://doi.org/10.5555/3055399.3055402

### 20. Portfolio Optimization using Python and CVXPY
**Type:** [ARTICLE]  
**Relevance:** Practical implementation example for portfolio optimization with CVXPY.  
**Note:** Practitioner/educational resource; exact source cited in the literature review is Medium.

- Medium search: https://medium.com/search?q=Portfolio%20Optimization%20using%20Python%20and%20CVXPY

### 21. BPQP: A Differentiable Convex Optimization Framework for Efficient End-to-End Learning
**Type:** [PREPRINT]  
**Year:** 2024  
**arXiv:** 2411.19285  
**Relevance:** Differentiable convex optimization for end-to-end learning.

- arXiv: https://arxiv.org/abs/2411.19285

---

## 4. Monte Carlo Simulation

### 22. Power of Monte Carlo Simulations in Finance
**Type:** [ARTICLE]  
**Publisher:** Interactive Brokers / IBKR Quant  
**Relevance:** Overview of Monte Carlo methods in finance, including risk and option applications.

- IBKR Quant: https://www.interactivebrokers.com/campus/ibkr-quant-news/power-of-monte-carlo-simulations-in-finance/

### 23. Stochastic Processes and Monte Carlo Method
**Type:** [RESOURCE/ARTICLE]  
**Publisher:** QuantConnect  
**Relevance:** Stochastic-process modeling and Monte Carlo implementation concepts.

- QuantConnect: https://www.quantconnect.com/learning/articles/introduction-to-options/stochastic-processes-and-monte-carlo-method

### 24. Monte Carlo Simulations for Assessing the Impact of Market Uncertainty on Investment Portfolios
**Type:** [PAPER — SOURCE CITATION INCOMPLETE]  
**Year:** 2025  
**Relevance:** Monte Carlo assessment of portfolio uncertainty and risk.

- ResearchGate search: https://www.researchgate.net/search/publication?q=Monte%20Carlo%20simulations%20for%20assessing%20the%20impact%20of%20market%20uncertainty%20on%20investment%20portfolios
- **Verification note:** The literature review supplies only the title, year and ResearchGate as the source; authors/journal/DOI are not given.

---

## 5. Execution Algorithms, VWAP, TWAP & Slippage

### 25. A Deep Dive into Execution Algorithms
**Type:** [ARTICLE]  
**Publisher:** Medium  
**Relevance:** Overview of execution algorithms including VWAP and TWAP.

- Medium search: https://medium.com/search?q=A%20Deep%20Dive%20into%20Execution%20Algorithms

### 26. Optimal Execution Algorithms: TWAP, VWAP & Market Impact
**Type:** [ARTICLE]  
**Relevance:** Practitioner explanation of execution algorithms and market impact.

- Site search: https://www.google.com/search?q=%22Optimal+Execution+Algorithms%3A+TWAP%2C+VWAP+%26+Market+Impact%22

### 27. Deep Learning for VWAP Execution in Crypto Markets: Beyond the Volume Curve
**Type:** [PREPRINT]  
**Author:** Rémi Genet  
**Year:** 2025  
**Relevance:** Directly optimizes VWAP execution using deep learning rather than forecasting the volume curve as an intermediate objective.

- arXiv: https://arxiv.org/abs/2502.13722
- SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5150912
- Code: https://github.com/remigenet/DeepLearningVWAP

### 28. TWAP Algorithm
**Type:** [ARTICLE]  
**Publisher:** Empirica  
**Relevance:** Explanation of Time-Weighted Average Price execution.

- Empirica search: https://www.google.com/search?q=site%3Aempirica.io+%22TWAP+Algorithm%22

### 29. Understanding Slippage in Finance: Key Insights and Examples
**Type:** [ARTICLE]  
**Publisher:** Investopedia  
**Relevance:** Background on slippage and execution-cost concepts.

- Investopedia search: https://www.investopedia.com/search?q=slippage%20finance

### 30. Optimal Execution of Portfolio Transactions
**Type:** [PAPER]  
**Authors:** Robert Almgren, Neil Chriss  
**Year:** 2001  
**Venue:** *Journal of Risk*, 3(2), 1–39  
**Relevance:** Foundational optimal-execution and market-impact framework.

- DOI: https://doi.org/10.21314/JOR.2001.041
- SSRN/search: https://www.google.com/search?q=%22Optimal+execution+of+portfolio+transactions%22+Almgren+Chriss

### 31. Reinforcement Learning for Trade Execution with Market Impact
**Type:** [PREPRINT — SOURCE CITATION INCOMPLETE]  
**Relevance:** Reinforcement-learning approaches to execution under market impact.

- arXiv search: https://arxiv.org/search/?query=Reinforcement+Learning+for+Trade+Execution+with+Market+Impact&searchtype=all
- **Verification note:** The literature review gives only the title and “arXiv”; no authors or identifier are supplied. Verify the exact paper before citing it.

---

## 6. Financial Machine Learning

### 32. Financial Machine Learning
**Type:** [PAPER/REVIEW]  
**Authors:** Bryan T. Kelly, Dacheng Xiu  
**Year:** 2023  
**Relevance:** Major review of machine learning in financial markets.

- NBER: https://www.nber.org/papers/w31502
- SSRN search: https://papers.ssrn.com/sol3/results.cfm?RequestTimeout=50000000

### 33. Financial Applications of Machine Learning: A Literature Review
**Type:** [PAPER/REVIEW]  
**Authors:** Noella Nazareth, Yeruva Venkata Ramana Reddy  
**Year:** 2023  
**Venue:** *Expert Systems with Applications*, 219, 119640  
**Relevance:** Broad literature review of ML applications across financial domains.

- ScienceDirect: https://www.sciencedirect.com/science/article/pii/S0957417423001410
- DOI: https://doi.org/10.1016/j.eswa.2023.119640

### 34. Advances in Financial Machine Learning
**Type:** [BOOK]  
**Author:** Marcos López de Prado  
**Year:** 2018  
**Publisher:** Wiley  
**Relevance:** Practical and methodological reference for financial ML, feature engineering, backtesting and risk.

- Wiley search: https://www.wiley.com/en-us/search?text=Advances+in+Financial+Machine+Learning

---

## 7. Risk Management

### 35. Risk Management in Quantitative Finance
**Type:** [ARTICLE]  
**Publisher:** PyQuant News  
**Relevance:** Introductory overview of quantitative-finance risk management.

- Site search: https://www.google.com/search?q=site%3Apyquantnews.com+%22Risk+Management+in+Quantitative+Finance%22

### 36. A Semi-Parametric Approach to Risk Management
**Type:** [PAPER — SOURCE CITATION INCOMPLETE]  
**Relevance:** Semi-parametric alternative to strongly distributional risk models.

- IOPscience search: https://www.google.com/search?q=site%3Aiopscience.iop.org+%22A+semi-parametric+approach+to+risk+management%22
- **Verification note:** The literature review does not provide authors, year, journal or DOI. Verify before academic citation.

### 37. Real-Time Financial Risk Modeling Using Deep Learning Techniques
**Type:** [PAPER]  
**Authors:** Sridhar N. Koka et al.  
**Year:** 2025 publication record; literature review labels it 2026  
**Relevance:** Deep learning for real-time financial risk modeling.

- ResearchGate: https://www.researchgate.net/publication/399702967_Real-Time_Financial_Risk_Modeling_Using_Deep_Learning_Techniques
- DOI: https://doi.org/10.1109/ICDISS68238.2025.11320637

### 38. Machine Learning for Financial Risk Management: A Survey
**Type:** [PAPER/REVIEW]  
**Authors:** Akib Mashrur, Wei Luo, Nayyar Zaidi, Antonio Robles-Kelly  
**Year:** 2020  
**Venue:** *IEEE Access*, 8, 203203–203223  
**Relevance:** Comprehensive taxonomy of ML applications in financial risk management.

- Deakin repository: https://dro.deakin.edu.au/articles/journal_contribution/Machine_learning_for_financial_risk_management_A_survey/20683219
- DOI: https://doi.org/10.1109/ACCESS.2020.3036322

### 39. Machine Learning: A Revolution in Risk Management and Compliance
**Type:** [ARTICLE/REPORT]  
**Publisher:** Institute of International Finance (IIF)  
**Relevance:** Industry perspective on ML for risk management and regulatory compliance.

- Search: https://www.google.com/search?q=site%3Aiif.com+%22Machine+Learning%3A+A+Revolution+in+Risk+Management+and+Compliance%22
- **Verification note:** The literature review does not provide a publication date or direct URL.

---

## 8. Multi-Agent Systems in Finance

### 40. Multi-Agent Systems for Computational Economics and Finance
**Type:** [PAPER]  
**Authors:** Michael Kampouridis, Panagiotis Kanellopoulos, Maria Kyropoulou, Themistoklis Melissourgos, Alexandros A. Voudouris  
**Year:** 2022  
**Relevance:** Foundations and applications of multi-agent systems in computational economics and finance.

- DOI/search: https://doi.org/10.3233/AIC-220117
- Publisher search: https://www.google.com/search?q=%22Multi-agent+systems+for+computational+economics+and+finance%22

### 41. Adaptive LLM-based Multi-Agent Systems to Enhance Quantitative Trading Performance
**Type:** [PAPER]  
**Authors:** Edward Yu-Cheng Cheng, Cheng-Jui Tseng, Hsueh-Ting Chu  
**Year:** 2026  
**Venue:** *PeerJ Computer Science*  
**Relevance:** Adaptive LLM-based multi-agent architecture for quantitative trading.

- PeerJ: https://peerj.com/articles/cs-3630/
- PDF: https://peerj.com/articles/cs-3630.pdf
- DOI: https://doi.org/10.7717/peerj-cs.3630

### 42. Large Language Model-Based Multi-Agent Systems for Financial Markets Simulation: A Survey
**Type:** [PAPER/REVIEW]  
**Authors:** Qinyuan Liu, Lihang Yao, Zidong Wang, Yufan Yang, Y. Tang, D. Cheng, C. Jiang  
**Year:** 2026  
**Venue:** *Science China Information Sciences*  
**Relevance:** Survey of LLM-based multi-agent financial-market simulation.

- DOI: https://doi.org/10.1007/s11432-026-4986-x
- Springer search: https://link.springer.com/search?query=Large+language+model-based+multi-agent+systems+for+financial+markets+simulation

---

## 9. Production ML Systems / MLOps

### 43. MLOps in Finance: A Strategic Guide to Scaling ML from Experiments to Production
**Type:** [ARTICLE]  
**Publisher:** ZenML  
**Relevance:** Productionization, governance, deployment and scaling of ML in financial environments.

- ZenML: https://www.zenml.io/blog/mlops-in-finance-a-strategic-guide-to-scaling-ml-from-experiments-to-production

### 44. MLOps in Finance: Automating Compliance & Fraud Detection
**Type:** [PAPER]  
**Author:** Balajee Asish Brahmandam  
**Year:** 2025  
**Venue:** *International Journal of Computer Trends and Technology*, 73(4), 35–41  
**Relevance:** MLOps for compliance, fraud detection and model lifecycle governance.

- Publisher: https://www.ijcttjournal.org/archives/ijctt-v73i4p105
- DOI: https://doi.org/10.14445/22312803/IJCTT-V73I4P105
- ResearchGate: https://www.researchgate.net/publication/391596554_MLOps_in_Finance_Automating_Compliance_Fraud_Detection

### 45. Scaling Financial Machine Learning with MLOps
**Type:** [ARTICLE]  
**Author:** William Arias  
**Year:** 2024  
**Publisher:** FINOS  
**Relevance:** Production MLOps, DevSecOps/data engineering integration and operational scaling of financial ML.

- FINOS: https://www.finos.org/blog/scaling-financial-machine-learning-with-mlops

### 46. The Aegis Framework: A Multi-Cloud, Fault-Tolerant MLOps Architecture for Real-Time Financial Decisioning and Regulatory Compliance
**Type:** [PAPER]  
**Author:** Suresh Chaganti  
**Year:** 2025 publication record  
**Venue:** *International Journal of Engineering & Extended Technologies Research*  
**Relevance:** Multi-cloud, fault-tolerant MLOps architecture for financial decisioning and regulatory compliance.

- IJEETR: https://www.ijeetr.com/index.php/ijeetr/article/view/266
- DOI: https://doi.org/10.15662/IJEETR.2025.0706031

---

# AegisQuant Reading Priority

The original literature review identifies a smaller subset as especially important for AegisQuant implementation. The strongest implementation-oriented starting set is:

1. Hamilton (1989) — regime switching
2. Markowitz (1952) — portfolio construction
3. Boyd & Vandenberghe (2004) — convex optimization
4. Diamond & Boyd (2016) — CVXPY
5. Almgren & Chriss (2001) — optimal execution
6. Kelly & Xiu — financial machine learning
7. Deep Learning Financial Time Series benchmark — xLSTM/deep-learning comparison
8. Contrastive Learning of Asset Embeddings — representation learning
9. Fin-JEPA — financial time-series representation learning
10. Adaptive Regime-Aware Prediction — regime-aware deep learning
11. Deep Learning for VWAP Execution — modern execution
12. Machine Learning for Financial Risk Management — risk taxonomy
13. LLM-Based Multi-Agent Financial Markets Survey — multi-agent architecture
14. QuantAgents — simulated multi-agent trading
15. The Aegis Framework — production MLOps architecture

## Verification Status

The source literature review itself contains several incomplete citations. In particular, entries **10, 24, 26, 28, 31, 35, 36 and 39** should not be treated as fully verified bibliographic records until their authors, publication metadata and canonical URLs are established.

The review also labels some works as 2026 even where the identifiable publication record is earlier. This library uses the **verified publication metadata where it could be established**, while preserving the source citation as the originating reference.

## Source

Primary source for the 46-entry list:

`aegisquant_literature_review.pdf` — *AegisQuant: Systematic Literature Review: An Autonomous Regime-Aware Quantitative Intelligence and Portfolio Optimization Platform*, July 8, 2026.

The source document explicitly contains an annotated bibliography numbered 1–46 and maps those works to AegisQuant modules.

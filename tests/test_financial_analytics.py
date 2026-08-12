import sys, os
sys.path.insert(0, os.path.abspath("."))

import unittest
from workspace.financial_analytics.analyzer import FinancialAnalyzer, FinancialMetrics
from workspace.financial_analytics.report_generator import FinancialReportGenerator


class TestFinancialAnalytics(unittest.TestCase):
    def test_calculate_metrics_accuracy(self):
        metrics = FinancialAnalyzer.calculate_metrics(
            mrr=50000.0,
            gross_margin_pct=80.0,
            operating_expenses=25000.0,
            new_customers_per_month=50.0,
            sales_marketing_cost=15000.0,
            churn_rate_pct=2.0,
            arpu=1000.0,
        )
        self.assertEqual(metrics.mrr, 50000.0)
        self.assertEqual(metrics.arr, 600000.0)
        self.assertEqual(metrics.gross_margin_pct, 80.0)
        self.assertEqual(metrics.ebitda_margin_pct, 30.0)  # (40000 - 25000) / 50000 = 30%
        self.assertEqual(metrics.cac, 300.0)  # 15000 / 50 = 300
        self.assertEqual(metrics.ltv, 40000.0)  # 1000 * 0.8 * (1 / 0.02) = 40000
        self.assertAlmostEqual(metrics.ltv_cac_ratio, 133.33, places=1)

    def test_monte_carlo_simulation_bounds(self):
        projection = FinancialAnalyzer.run_monte_carlo_simulation(
            starting_mrr=10000.0,
            months=12,
            num_simulations=100,
            seed=123,
        )
        self.assertEqual(projection.starting_mrr, 10000.0)
        self.assertGreater(projection.p90_final_mrr, projection.p50_final_mrr)
        self.assertGreater(projection.p50_final_mrr, projection.p10_final_mrr)

    def test_report_generation(self):
        metrics = FinancialAnalyzer.calculate_metrics(
            mrr=10000.0, gross_margin_pct=85.0, operating_expenses=4000.0,
            new_customers_per_month=10.0, sales_marketing_cost=2000.0, churn_rate_pct=1.5, arpu=1000.0,
        )
        projection = FinancialAnalyzer.run_monte_carlo_simulation(starting_mrr=10000.0)
        report = FinancialReportGenerator.generate_markdown_report("TechCorp SaaS", metrics, projection)
        self.assertIn("TechCorp SaaS", report)
        self.assertIn("MRR (Monthly Recurring Revenue)", report)


if __name__ == "__main__":
    unittest.main()

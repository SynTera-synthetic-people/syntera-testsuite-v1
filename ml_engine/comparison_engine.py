"""Comparison Engine - Comprehensive Statistical Tests"""
import numpy as np
from scipy.stats import (
    chi2_contingency, ks_2samp, mannwhitneyu, ttest_ind,
    anderson_ksamp, pearsonr, spearmanr, wasserstein_distance,
    shapiro, cramervonmises_2samp
)
from scipy.special import rel_entr
from scipy.spatial.distance import jensenshannon
import logging
import math

logger = logging.getLogger(__name__)


def safe_float(value):
    """Convert value to float, replacing NaN and inf with None or 0."""
    if value is None:
        return None
    try:
        fval = float(value)
        if math.isnan(fval):
            return None
        elif math.isinf(fval):
            return None
        return fval
    except (ValueError, TypeError):
        return None


class ComparisonEngine:
    def chi_square_test(self, synthetic_data, real_data):
        try:
            # Convert to numpy arrays
            syn_arr = np.array(synthetic_data)
            real_arr = np.array(real_data)
            
            # Create bins for frequency comparison
            # Combine both datasets to get common bins
            all_values = np.concatenate([syn_arr, real_arr])
            if len(all_values) == 0:
                return {"test": "chi_square", "error": "Empty data"}
            
            # Create bins (use 10 bins or fewer if data is small)
            n_bins = min(10, len(np.unique(all_values)))
            if n_bins < 2:
                n_bins = 2
            
            # Get histogram counts for both datasets
            syn_counts, _ = np.histogram(syn_arr, bins=n_bins)
            real_counts, _ = np.histogram(real_arr, bins=n_bins)
            
            # Create contingency table
            contingency = np.array([syn_counts, real_counts])
            
            # Run chi-square test
            chi2, p_value, dof, expected = chi2_contingency(contingency)
            
            # For chi-square: Higher p-value means more similar distributions
            # p > 0.05: Cannot reject null (distributions are similar) - TIER_1
            # p > 0.01: Weak evidence against similarity - TIER_2
            # p <= 0.01: Strong evidence against similarity - TIER_3
            tier = "TIER_1" if p_value > 0.05 else "TIER_2" if p_value > 0.01 else "TIER_3"
            # Match score is the p-value (higher is better)
            match_score = safe_float(p_value) or 0.0
            return {
                "test": "chi_square", 
                "chi2": safe_float(chi2) or 0.0, 
                "p_value": safe_float(p_value) or 0.0,
                "tier": tier, 
                "match_score": match_score,
                "interpretation": "Compares frequency distributions between synthetic and real data. Higher p-value means more similar distributions."
            }
        except Exception as e:
            logger.error(f"Chi-square test error: {str(e)}")
            return {"test": "chi_square", "error": str(e)}

    def ks_test(self, synthetic_data, real_data):
        try:
            ks_stat, p_value = ks_2samp(synthetic_data, real_data)
            tier = "TIER_1" if ks_stat < 0.10 else "TIER_2" if ks_stat < 0.20 else "TIER_3"
            match_score = safe_float(1 - ks_stat) or 0.0
            return {"test": "ks_test", "ks_statistic": safe_float(ks_stat) or 0.0, "p_value": safe_float(p_value) or 0.0,
                   "tier": tier, "match_score": match_score}
        except Exception as e:
            return {"test": "ks_test", "error": str(e)}

    def jensen_shannon_divergence(self, synthetic_probs, real_probs):
        """Jensen-Shannon divergence - works with raw data arrays or probability distributions."""
        try:
            # Convert to numpy arrays
            syn_arr = np.array(synthetic_probs)
            real_arr = np.array(real_probs)
            
            # Normalize to create probability distributions (handle sum = 0 case)
            syn_sum = np.sum(syn_arr)
            real_sum = np.sum(real_arr)
            
            if syn_sum == 0 or real_sum == 0:
                return {"test": "jensen_shannon", "error": "Cannot normalize: one or both arrays sum to zero"}
            
            p = syn_arr / syn_sum
            q = real_arr / real_sum
            
            # Ensure arrays have same length for JS divergence
            max_len = max(len(p), len(q))
            if len(p) < max_len:
                p = np.pad(p, (0, max_len - len(p)), 'constant')
            if len(q) < max_len:
                q = np.pad(q, (0, max_len - len(q)), 'constant')
            
            js_div = jensenshannon(p, q)
            
            # JS divergence ranges from 0 (identical) to 1 (maximally different)
            # Lower divergence = better match
            tier = "TIER_1" if js_div < 0.05 else "TIER_2" if js_div < 0.15 else "TIER_3"
            match_score = safe_float(1 - min(js_div, 1.0)) or 0.0
            return {"test": "jensen_shannon", "divergence": safe_float(js_div) or 0.0, "tier": tier,
                   "match_score": match_score, "interpretation": "Measures similarity between probability distributions. Lower divergence means higher similarity."}
        except Exception as e:
            logger.error(f"Jensen-Shannon divergence error: {str(e)}")
            return {"test": "jensen_shannon", "error": str(e)}

    def mann_whitney_test(self, synthetic_data, real_data):
        """Mann-Whitney U test for independent samples."""
        try:
            if len(synthetic_data) < 3 or len(real_data) < 3:
                return {"test": "mann_whitney", "error": "Insufficient data (need at least 3 samples)"}
            statistic, p_value = mannwhitneyu(synthetic_data, real_data, alternative='two-sided')
            # Higher p-value means medians are similar
            # p > 0.05: Cannot reject null (medians are similar) - TIER_1
            # p > 0.01: Weak evidence against similarity - TIER_2
            # p <= 0.01: Strong evidence against similarity - TIER_3
            tier = "TIER_1" if p_value > 0.05 else "TIER_2" if p_value > 0.01 else "TIER_3"
            match_score = safe_float(p_value) or 0.0
            return {
                "test": "mann_whitney",
                "statistic": safe_float(statistic) or 0.0,
                "p_value": safe_float(p_value) or 0.0,
                "tier": tier,
                "match_score": match_score,
                "interpretation": "Tests if distributions have the same median. Higher p-value means similar medians."
            }
        except Exception as e:
            return {"test": "mann_whitney", "error": str(e)}

    def t_test(self, synthetic_data, real_data):
        """Independent samples t-test."""
        try:
            if len(synthetic_data) < 2 or len(real_data) < 2:
                return {"test": "t_test", "error": "Insufficient data (need at least 2 samples)"}
            statistic, p_value = ttest_ind(synthetic_data, real_data)
            # Higher p-value means means are similar
            # p > 0.05: Cannot reject null (means are similar) - TIER_1
            # p > 0.01: Weak evidence against similarity - TIER_2
            # p <= 0.01: Strong evidence against similarity - TIER_3
            tier = "TIER_1" if p_value > 0.05 else "TIER_2" if p_value > 0.01 else "TIER_3"
            match_score = safe_float(p_value) or 0.0
            return {
                "test": "t_test",
                "statistic": safe_float(statistic) or 0.0,
                "p_value": safe_float(p_value) or 0.0,
                "tier": tier,
                "match_score": match_score,
                "interpretation": "Tests if distributions have the same mean. Higher p-value means similar means."
            }
        except Exception as e:
            return {"test": "t_test", "error": str(e)}

    def anderson_darling_test(self, synthetic_data, real_data):
        """Anderson-Darling k-sample test."""
        try:
            if len(synthetic_data) < 3 or len(real_data) < 3:
                return {"test": "anderson_darling", "error": "Insufficient data"}
            result = anderson_ksamp([synthetic_data, real_data])
            statistic = result.statistic
            p_value = result.pvalue if hasattr(result, 'pvalue') else None
            
            # Anderson-Darling: Lower statistic means more similar distributions
            # Use statistic-based tiering since p-value might not be available
            # Lower statistic = better match
            if p_value:
                tier = "TIER_1" if p_value > 0.05 else "TIER_2" if p_value > 0.01 else "TIER_3"
                match_score = safe_float(p_value) or 0.0
            else:
                # Fallback to statistic-based tiering
                # Normalize statistic (assuming range 0-10 for typical values)
                norm_stat = min(statistic / 5.0, 1.0) if statistic < 5.0 else 1.0
                match_score = safe_float(1.0 - norm_stat) or 0.0
                tier = "TIER_1" if match_score > 0.80 else "TIER_2" if match_score > 0.60 else "TIER_3"
            
            return {
                "test": "anderson_darling",
                "statistic": safe_float(statistic) or 0.0,
                "p_value": safe_float(p_value) if p_value else None,
                "tier": tier,
                "match_score": match_score,
                "interpretation": "Tests if samples come from the same distribution. Lower statistic or higher p-value means similar distributions."
            }
        except Exception as e:
            return {"test": "anderson_darling", "error": str(e)}

    def wasserstein_distance_test(self, synthetic_data, real_data):
        """Wasserstein (Earth Mover's) distance."""
        try:
            if len(synthetic_data) == 0 or len(real_data) == 0:
                return {"test": "wasserstein_distance", "error": "Empty data"}
            distance = wasserstein_distance(synthetic_data, real_data)
            # Normalize by data range for better interpretation
            data_range = max(max(synthetic_data), max(real_data)) - min(min(synthetic_data), min(real_data))
            normalized = distance / data_range if data_range > 0 else distance
            tier = "TIER_1" if normalized < 0.10 else "TIER_2" if normalized < 0.25 else "TIER_3"
            match_score = safe_float(1 - min(normalized, 1.0)) or 0.0
            return {
                "test": "wasserstein_distance",
                "distance": safe_float(distance) or 0.0,
                "normalized_distance": safe_float(normalized) or 0.0,
                "tier": tier,
                "match_score": match_score,
                "interpretation": "Measures minimum cost to transform one distribution to another"
            }
        except Exception as e:
            return {"test": "wasserstein_distance", "error": str(e)}

    def correlation_test(self, synthetic_data, real_data):
        """Pearson and Spearman correlation tests."""
        try:
            if len(synthetic_data) != len(real_data):
                # Align by length
                min_len = min(len(synthetic_data), len(real_data))
                synthetic_data = synthetic_data[:min_len]
                real_data = real_data[:min_len]
            
            if len(synthetic_data) < 3:
                return {"test": "correlation", "error": "Insufficient data"}
            
            pearson_r, pearson_p = pearsonr(synthetic_data, real_data)
            spearman_r, spearman_p = spearmanr(synthetic_data, real_data)
            
            # Use average correlation for tier
            avg_corr = (abs(pearson_r) + abs(spearman_r)) / 2
            tier = "TIER_1" if avg_corr > 0.95 else "TIER_2" if avg_corr > 0.85 else "TIER_3"
            match_score = safe_float(avg_corr) or 0.0
            
            return {
                "test": "correlation",
                "pearson_r": safe_float(pearson_r) or 0.0,
                "pearson_p": safe_float(pearson_p) or 0.0,
                "spearman_r": safe_float(spearman_r) or 0.0,
                "spearman_p": safe_float(spearman_p) or 0.0,
                "average_correlation": match_score,
                "tier": tier,
                "match_score": match_score,
                "interpretation": "Measures linear (Pearson) and monotonic (Spearman) relationships"
            }
        except Exception as e:
            return {"test": "correlation", "error": str(e)}

    def error_metrics(self, synthetic_data, real_data):
        """Mean Absolute Error and Root Mean Square Error."""
        try:
            if len(synthetic_data) != len(real_data):
                min_len = min(len(synthetic_data), len(real_data))
                synthetic_data = synthetic_data[:min_len]
                real_data = real_data[:min_len]
            
            if len(synthetic_data) == 0:
                return {"test": "error_metrics", "error": "Empty data"}
            
            mae = np.mean(np.abs(np.array(synthetic_data) - np.array(real_data)))
            rmse = np.sqrt(np.mean((np.array(synthetic_data) - np.array(real_data)) ** 2))
            
            # Normalize by data range
            data_range = max(max(synthetic_data), max(real_data)) - min(min(synthetic_data), min(real_data))
            normalized_mae = safe_float(mae / data_range) if data_range > 0 else safe_float(mae) or 0.0
            normalized_rmse = safe_float(rmse / data_range) if data_range > 0 else safe_float(rmse) or 0.0
            
            # Tier based on normalized error
            avg_error = safe_float((normalized_mae + normalized_rmse) / 2.0) or 0.0
            tier = "TIER_1" if avg_error < 0.10 else "TIER_2" if avg_error < 0.25 else "TIER_3"
            match_score = safe_float(1 - min(avg_error, 1.0)) or 0.0
            
            return {
                "test": "error_metrics",
                "mae": safe_float(mae) or 0.0,
                "rmse": safe_float(rmse) or 0.0,
                "normalized_mae": normalized_mae,
                "normalized_rmse": normalized_rmse,
                "tier": tier,
                "match_score": match_score,
                "interpretation": "Measures prediction accuracy (lower is better)"
            }
        except Exception as e:
            return {"test": "error_metrics", "error": str(e)}

    def distribution_summary(self, synthetic_data, real_data):
        """Summary statistics comparison."""
        try:
            syn_mean = safe_float(np.mean(synthetic_data)) if len(synthetic_data) > 0 else 0.0
            syn_std = safe_float(np.std(synthetic_data)) if len(synthetic_data) > 1 else 0.0
            syn_median = safe_float(np.median(synthetic_data)) if len(synthetic_data) > 0 else 0.0
            
            real_mean = safe_float(np.mean(real_data)) if len(real_data) > 0 else 0.0
            real_std = safe_float(np.std(real_data)) if len(real_data) > 1 else 0.0
            real_median = safe_float(np.median(real_data)) if len(real_data) > 0 else 0.0
            
            # Ensure all values are not None before arithmetic
            syn_mean = syn_mean or 0.0
            syn_std = syn_std or 0.0
            syn_median = syn_median or 0.0
            real_mean = real_mean or 0.0
            real_std = real_std or 0.0
            real_median = real_median or 0.0
            
            mean_diff = abs(syn_mean - real_mean)
            std_diff = abs(syn_std - real_std)
            median_diff = abs(syn_median - real_median)
            
            # Normalize differences - avoid division by zero
            mean_range = max(abs(syn_mean), abs(real_mean)) if max(abs(syn_mean), abs(real_mean)) > 0 else 1.0
            std_range = max(syn_std, real_std) if max(syn_std, real_std) > 0 else 1.0
            
            normalized_mean_diff = safe_float(mean_diff / mean_range) if mean_range > 0 else 0.0
            normalized_std_diff = safe_float(std_diff / std_range) if std_range > 0 else 0.0
            
            normalized_mean_diff = normalized_mean_diff or 0.0
            normalized_std_diff = normalized_std_diff or 0.0
            
            avg_diff = safe_float((normalized_mean_diff + normalized_std_diff) / 2.0) or 0.0
            tier = "TIER_1" if avg_diff < 0.10 else "TIER_2" if avg_diff < 0.25 else "TIER_3"
            
            match_score = safe_float(1 - min(avg_diff, 1.0)) or 0.0
            
            return {
                "test": "distribution_summary",
                "synthetic_mean": syn_mean,
                "synthetic_std": syn_std,
                "synthetic_median": syn_median,
                "real_mean": real_mean,
                "real_std": real_std,
                "real_median": real_median,
                "mean_difference": mean_diff,
                "std_difference": std_diff,
                "median_difference": median_diff,
                "normalized_mean_diff": normalized_mean_diff,
                "normalized_std_diff": normalized_std_diff,
                "tier": tier,
                "match_score": match_score,
                "interpretation": "Compares mean, standard deviation, and median"
            }
        except Exception as e:
            return {"test": "distribution_summary", "error": str(e)}

    def kullback_leibler_divergence(self, synthetic_data, real_data):
        """Kullback-Leibler divergence between two distributions."""
        try:
            syn_arr = np.array(synthetic_data)
            real_arr = np.array(real_data)
            
            # Normalize to create probability distributions
            syn_sum = np.sum(syn_arr)
            real_sum = np.sum(real_arr)
            
            if syn_sum == 0 or real_sum == 0:
                return {"test": "kullback_leibler", "error": "Cannot normalize: one or both arrays sum to zero"}
            
            p = syn_arr / syn_sum
            q = real_arr / real_sum
            
            # Ensure arrays have same length
            max_len = max(len(p), len(q))
            if len(p) < max_len:
                p = np.pad(p, (0, max_len - len(p)), 'constant', constant_values=1e-10)
            if len(q) < max_len:
                q = np.pad(q, (0, max_len - len(q)), 'constant', constant_values=1e-10)
            
            # Avoid zero values for KL divergence
            p = np.clip(p, 1e-10, None)
            q = np.clip(q, 1e-10, None)
            
            # Calculate KL divergence: KL(P||Q) = sum(P * log(P/Q))
            kl_div = np.sum(rel_entr(p, q))
            
            # KL divergence ranges from 0 (identical) to infinity
            # Normalize and convert to match score (lower divergence = better match)
            # Use tanh to bound KL divergence to [0, 1]
            normalized_kl = safe_float(np.tanh(min(kl_div, 10.0) / 5.0)) or 0.0
            tier = "TIER_1" if normalized_kl < 0.10 else "TIER_2" if normalized_kl < 0.30 else "TIER_3"
            match_score = safe_float(1 - normalized_kl) or 0.0
            
            return {
                "test": "kullback_leibler",
                "divergence": safe_float(kl_div) or 0.0,
                "normalized_divergence": normalized_kl,
                "tier": tier,
                "match_score": match_score,
                "interpretation": "Measures information gain when using real data to approximate synthetic data. Lower is better."
            }
        except Exception as e:
            logger.error(f"Kullback-Leibler divergence error: {str(e)}")
            return {"test": "kullback_leibler", "error": str(e)}

    def cramer_von_mises_test(self, synthetic_data, real_data):
        """Cramér-von Mises two-sample test."""
        try:
            if len(synthetic_data) < 3 or len(real_data) < 3:
                return {"test": "cramer_von_mises", "error": "Insufficient data (need at least 3 samples)"}
            
            result = cramervonmises_2samp(synthetic_data, real_data)
            statistic = result.statistic
            p_value = result.pvalue if hasattr(result, 'pvalue') else None
            
            # Lower statistic and higher p-value means more similar distributions
            if p_value:
                tier = "TIER_1" if p_value > 0.05 else "TIER_2" if p_value > 0.01 else "TIER_3"
                match_score = safe_float(p_value) or 0.0
            else:
                # Normalize statistic (typical range 0-1)
                norm_stat = min(statistic / 2.0, 1.0)
                match_score = safe_float(1.0 - norm_stat) or 0.0
                tier = "TIER_1" if match_score > 0.80 else "TIER_2" if match_score > 0.60 else "TIER_3"
            
            return {
                "test": "cramer_von_mises",
                "statistic": safe_float(statistic) or 0.0,
                "p_value": safe_float(p_value) if p_value else None,
                "tier": tier,
                "match_score": match_score,
                "interpretation": "Tests if samples come from the same distribution. Higher p-value or lower statistic means similar distributions."
            }
        except Exception as e:
            logger.error(f"Cramér-von Mises test error: {str(e)}")
            return {"test": "cramer_von_mises", "error": str(e)}

    def compare_distributions(self, synthetic_data, real_data):
        """Comprehensive comparison using multiple statistical tests."""
        results = {
            "synthetic_size": len(synthetic_data),
            "real_size": len(real_data),
            "tests": []
        }
        
        # Convert to lists for consistency
        syn_list = list(synthetic_data) if synthetic_data else []
        real_list = list(real_data) if real_data else []
        
        if len(syn_list) == 0 or len(real_list) == 0:
            results["tests"].append({
                "test": "data_validation",
                "error": "One or both datasets are empty"
            })
            results["overall_tier"] = "TIER_4"
            return results
        
        # Run all statistical tests
        results["tests"].append(self.chi_square_test(syn_list, real_list))
        results["tests"].append(self.ks_test(syn_list, real_list))
        results["tests"].append(self.jensen_shannon_divergence(syn_list, real_list))
        results["tests"].append(self.mann_whitney_test(syn_list, real_list))
        results["tests"].append(self.t_test(syn_list, real_list))
        results["tests"].append(self.anderson_darling_test(syn_list, real_list))
        results["tests"].append(self.wasserstein_distance_test(syn_list, real_list))
        results["tests"].append(self.correlation_test(syn_list, real_list))
        results["tests"].append(self.error_metrics(syn_list, real_list))
        results["tests"].append(self.distribution_summary(syn_list, real_list))
        results["tests"].append(self.kullback_leibler_divergence(syn_list, real_list))
        results["tests"].append(self.cramer_von_mises_test(syn_list, real_list))
        
        # Calculate overall tier based on all tests
        tiers = [t.get("tier") for t in results["tests"] if "tier" in t and "error" not in t]
        
        if len(tiers) == 0:
            results["overall_tier"] = "TIER_4"
            return results
        
        tier_counts = {
            "TIER_1": tiers.count("TIER_1"),
            "TIER_2": tiers.count("TIER_2"),
            "TIER_3": tiers.count("TIER_3"),
            "TIER_4": tiers.count("TIER_4"),
        }
        
        # Calculate overall accuracy based on actual match scores from all tests
        match_scores = []
        for test in results["tests"]:
            if "match_score" in test and "error" not in test:
                score = test["match_score"]
                # Safely convert and validate score
                if score is not None:
                    try:
                        score_float = float(score)
                        if not math.isnan(score_float) and not math.isinf(score_float):
                            match_scores.append(max(0.0, min(1.0, score_float)))  # Clamp between 0 and 1
                    except (ValueError, TypeError):
                        pass  # Skip invalid scores
        
        # Calculate weighted average match score
        if match_scores and len(match_scores) > 0:
            # Weight tests equally, but you could weight by importance
            overall_accuracy_score = sum(match_scores) / len(match_scores)
            # Ensure accuracy is between 0 and 1
            overall_accuracy_score = max(0.0, min(1.0, overall_accuracy_score))
            logger.info(f"Calculated accuracy from {len(match_scores)} tests: {overall_accuracy_score:.1%} (scores: {[f'{s:.2f}' for s in match_scores[:5]]}...)")
        else:
            # If no valid match scores, default to low accuracy
            overall_accuracy_score = 0.5
            logger.warning("No valid match scores found, defaulting to 50% accuracy")
        
        # Tier calculation based on both tier distribution and actual accuracy score
        tier_1_ratio = tier_counts["TIER_1"] / len(tiers) if len(tiers) > 0 else 0
        tier_2_ratio = tier_counts["TIER_2"] / len(tiers) if len(tiers) > 0 else 0
        
        # Overall tier by accuracy: >85% TIER_1, >75% TIER_2, >50% TIER_3, else TIER_4
        if overall_accuracy_score > 0.85:
            overall_tier = "TIER_1"
        elif overall_accuracy_score > 0.75:
            overall_tier = "TIER_2"
        elif overall_accuracy_score > 0.50:
            overall_tier = "TIER_3"
        else:
            overall_tier = "TIER_4"
        
        results["overall_tier"] = overall_tier
        results["overall_accuracy"] = overall_accuracy_score  # Store calculated accuracy
        results["tier_distribution"] = tier_counts
        results["test_summary"] = {
            "total_tests": len(results["tests"]),
            "successful_tests": len(tiers),
            "failed_tests": len(results["tests"]) - len(tiers),
            "tier_1_count": tier_counts["TIER_1"],
            "tier_2_count": tier_counts["TIER_2"],
            "tier_3_count": tier_counts["TIER_3"],
            "tier_4_count": tier_counts["TIER_4"],
            "average_match_score": overall_accuracy_score,
            "tier_1_ratio": tier_1_ratio,
            "tier_2_ratio": tier_2_ratio,
        }
        
        # Add recommendations based on overall tier and accuracy
        recommendations = []
        if overall_tier == "TIER_1":
            recommendations.append(f"Your synthetic data is an excellent match for the real data (accuracy: {overall_accuracy_score:.1%}). It's ready for use in critical applications!")
        elif overall_tier == "TIER_2":
            recommendations.append(f"Your synthetic data shows a good match (accuracy: {overall_accuracy_score:.1%}), but there's room for improvement. Consider refining your data generation process or reviewing specific test results for areas to enhance.")
            recommendations.append(f"Focus on tests that returned 'TIER_2', 'TIER_3' or 'TIER_4' to pinpoint specific discrepancies.")
        elif overall_tier == "TIER_3":
            recommendations.append(f"Your synthetic data needs improvement to match the real data (accuracy: {overall_accuracy_score:.1%}). Review the detailed test results to identify discrepancies and adjust your data generation strategy.")
            recommendations.append(f"Pay close attention to tests with 'TIER_3' or 'TIER_4' status and consider generating more diverse or representative synthetic samples.")
        else:  # TIER_4
            recommendations.append(f"Your synthetic data needs significant improvement (accuracy: {overall_accuracy_score:.1%}). Review the detailed test results to identify major discrepancies and adjust your data generation strategy.")
            recommendations.append(f"Focus on tests with 'TIER_4' status ({tier_counts['TIER_4']} out of {len(tiers)} tests) and consider generating more diverse or representative synthetic samples.")
        
        results["recommendations"] = recommendations
        
        return results


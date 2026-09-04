#!/usr/bin/env python3
"""
Gate Learner: Autonomous learning system that improves gate rules over time.

Analyzes violation patterns and automatically updates detection logic.
Runs continuously to adapt gate rules based on real-world violations.
"""
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Any, Tuple


class GateLearner:
    """Learns from violations and improves gate rules automatically."""

    def __init__(self):
        self.learning_db_path = Path(".claude/gate_learning.json")
        self.rules_path = Path(".claude/gate_learned_rules.json")
        self.patterns = defaultdict(int)
        self.fix_success_rate = defaultdict(lambda: {'success': 0, 'total': 0})
        self.load_history()

    def load_history(self):
        """Load violation history from learning database."""
        if self.learning_db_path.exists():
            try:
                with open(self.learning_db_path) as f:
                    data = json.load(f)
                    self._analyze_patterns(data.get('issues', []))
            except Exception as e:
                print(f"Failed to load learning history: {e}")

    def _analyze_patterns(self, issues: List[Dict]):
        """Analyze violation patterns to find trends."""
        for issue in issues:
            issue_type = issue.get('issue_type', 'unknown')
            self.patterns[issue_type] += 1

            # Track fix success rates
            if 'severity' in issue:
                key = f"{issue_type}_{issue['severity']}"
                self.fix_success_rate[key]['total'] += 1
                if issue.get('fixed'):
                    self.fix_success_rate[key]['success'] += 1

    def get_success_rate(self, issue_type: str, severity: str = None) -> float:
        """Get fix success rate for an issue type."""
        key = f"{issue_type}_{severity}" if severity else issue_type
        data = self.fix_success_rate.get(key, {'success': 0, 'total': 0})
        if data['total'] == 0:
            return 0.0
        return data['success'] / data['total']

    def learn_and_update_rules(self) -> Dict[str, Any]:
        """Analyze patterns and generate updated rules."""
        learned_rules = {
            'timestamp': datetime.now().isoformat(),
            'pattern_analysis': {},
            'rule_updates': [],
            'detection_improvements': [],
            'learning_insights': []
        }

        # Analyze most common violation types
        if self.patterns:
            sorted_patterns = sorted(self.patterns.items(), key=lambda x: x[1], reverse=True)
            learned_rules['pattern_analysis']['top_violations'] = [
                {'type': t, 'count': c, 'success_rate': self.get_success_rate(t)}
                for t, c in sorted_patterns[:10]
            ]

        # Generate rule improvements based on patterns
        for issue_type, count in self.patterns.items():
            success_rate = self.get_success_rate(issue_type)

            # If success rate is low, suggest stricter detection
            if success_rate < 0.5 and count > 5:
                learned_rules['rule_updates'].append({
                    'type': issue_type,
                    'action': 'increase_detection_strictness',
                    'reason': f'Low fix rate ({success_rate:.1%}) despite {count} violations',
                    'suggestion': f'Make {issue_type} detection more aggressive'
                })

            # If success rate is high, can relax slightly
            if success_rate > 0.9 and count > 10:
                learned_rules['rule_updates'].append({
                    'type': issue_type,
                    'action': 'optimize_detection',
                    'reason': f'High fix rate ({success_rate:.1%}), rule is effective',
                    'suggestion': f'Rule for {issue_type} is working well, maintain current strictness'
                })

        # Generate insights
        self._generate_insights(learned_rules)

        # Save learned rules
        self._save_learned_rules(learned_rules)

        return learned_rules

    def _generate_insights(self, learned_rules: Dict):
        """Generate actionable insights from patterns."""
        total_violations = sum(self.patterns.values())
        if total_violations == 0:
            return

        # Most problematic area
        top_issue = max(self.patterns.items(), key=lambda x: x[1])
        learned_rules['learning_insights'].append({
            'insight': 'Top violation type',
            'issue': top_issue[0],
            'frequency': f"{top_issue[1]} violations ({top_issue[1]/total_violations*100:.1f}%)",
            'recommendation': f'Focus training on {top_issue[0]} pattern'
        })

        # Auto-fixable violations
        auto_fixable = self._identify_auto_fixable_patterns()
        if auto_fixable:
            learned_rules['learning_insights'].append({
                'insight': 'Auto-fixable patterns identified',
                'patterns': auto_fixable,
                'recommendation': 'Consider enabling auto-fix for these patterns'
            })

    def _identify_auto_fixable_patterns(self) -> List[str]:
        """Identify which violation patterns can be automatically fixed."""
        auto_fixable = [
            'Async call without error handling',
            'Missing error message',
            'Magic number',
            'Missing null check',
            'Silent catch block'
        ]
        return [p for p in auto_fixable if self.patterns.get(p, 0) > 0]

    def _save_learned_rules(self, rules: Dict):
        """Save learned rules to disk."""
        self.rules_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.rules_path, 'w') as f:
            json.dump(rules, f, indent=2)

    def should_auto_apply_fix(self, issue_type: str, severity: str) -> bool:
        """Decide if a fix should be auto-applied based on learning."""
        success_rate = self.get_success_rate(issue_type, severity)

        # Auto-apply if success rate is high and issue is not critical
        if severity == 'CRITICAL':
            return False  # Never auto-apply for critical issues

        if success_rate >= 0.85:
            return True

        return False

    def get_learning_statistics(self) -> Dict[str, Any]:
        """Get current learning statistics."""
        total_violations = sum(self.patterns.values())
        total_fixable = sum(
            self.fix_success_rate[k]['success']
            for k in self.fix_success_rate
        )
        total_attempted = sum(
            self.fix_success_rate[k]['total']
            for k in self.fix_success_rate
        )

        return {
            'total_violations_analyzed': total_violations,
            'total_fixes_attempted': total_attempted,
            'total_fixes_successful': total_fixable,
            'overall_fix_rate': total_fixable / total_attempted if total_attempted > 0 else 0,
            'top_violations': dict(sorted(self.patterns.items(), key=lambda x: x[1], reverse=True)[:5]),
            'last_updated': datetime.now().isoformat()
        }


class GateRuleUpdater:
    """Updates gate rules based on learned patterns."""

    def __init__(self, learner: GateLearner):
        self.learner = learner
        self.gate_config_path = Path("backend/scripts/.gate_config.json")

    def auto_update_rules(self) -> bool:
        """Automatically update gate rules based on learning."""
        learned_rules = self.learner.learn_and_update_rules()

        # Apply rule updates
        for update in learned_rules.get('rule_updates', []):
            self._apply_rule_update(update)

        return len(learned_rules.get('rule_updates', [])) > 0

    def _apply_rule_update(self, update: Dict[str, str]):
        """Apply a specific rule update."""
        issue_type = update.get('type')
        action = update.get('action')

        config = self._load_config()

        if issue_type not in config:
            config[issue_type] = {}

        if action == 'increase_detection_strictness':
            config[issue_type]['strictness'] = config[issue_type].get('strictness', 1) + 0.1
        elif action == 'optimize_detection':
            config[issue_type]['optimized'] = True

        self._save_config(config)

    def _load_config(self) -> Dict:
        """Load current gate configuration."""
        if self.gate_config_path.exists():
            with open(self.gate_config_path) as f:
                return json.load(f)
        return {}

    def _save_config(self, config: Dict):
        """Save updated configuration."""
        self.gate_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.gate_config_path, 'w') as f:
            json.dump(config, f, indent=2)


# Continuous learning loop
def run_continuous_learning():
    """Run the continuous learning loop (call every minute)."""
    learner = GateLearner()
    updater = GateRuleUpdater(learner)

    # Update rules based on learning
    if updater.auto_update_rules():
        print("[GATE LEARNER] Rules updated based on violation patterns")

    # Get and log statistics
    stats = learner.get_learning_statistics()
    print(f"[GATE LEARNER] Statistics: {stats['overall_fix_rate']*100:.1f}% fix rate")

    return stats

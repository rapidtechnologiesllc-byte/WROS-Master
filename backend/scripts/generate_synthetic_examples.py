#!/usr/bin/env python3
"""
import logging
Synthetic Training Data Generation using Claude

Takes real resume examples and generates 5000+ synthetic variations using Claude.
This vastly expands the training dataset without manual effort.

Process:
1. Read collected real examples (50-100)
2. For each example, use Claude to generate variations
3. Accumulate synthetic training data
4. Validate synthetic data quality
5. Output combined dataset for BERT fine-tuning

Usage:
    python generate_synthetic_examples.py --input training_data.json --output synthetic_data.json --count 5000

This solves the training data bottleneck:
- Real data: 50-100 examples (manual collection)
- Synthetic data: 5000+ examples (Claude-generated)
- Total: 5000-5100 examples for fine-tuning
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
import argparse
from datetime import datetime
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from anthropic import Anthropic

client = Anthropic()

logger = logging.getLogger(__name__)

class SyntheticDataGenerator:
    """Generate synthetic training examples using Claude"""

    def __init__(self, input_file: str, output_file: str, target_count: int = 5000):
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.target_count = target_count
        self.real_examples = []
        self.synthetic_examples = []

    def load_real_examples(self):
        """Load collected training data"""
        print(f" Loading real examples from {self.input_file}...")

        with open(self.input_file, 'r') as f:
            data = json.load(f)

        self.real_examples = data.get("examples", [])
        print(f" Loaded {len(self.real_examples)} real examples")

        return len(self.real_examples)

    def generate_synthetic_data(self):
        """
        Generate synthetic examples using Claude.

        Strategy:
        1. For each real example, create a template
        2. Use Claude to generate variations
        3. Ensure output is valid training format
        """
        if not self.real_examples:
            raise ValueError("No real examples loaded")

        print(f"\n Generating {self.target_count} synthetic examples...")
        print(f"   Strategy: Variations from {len(self.real_examples)} real examples")

        # Calculate variations per example
        variations_per_example = max(1, self.target_count // len(self.real_examples))
        print(f"   Rate: ~{variations_per_example} variations per real example")

        for i, real_example in enumerate(self.real_examples, 1):
            print(f"\n   [{i}/{len(self.real_examples)}] Processing example: {real_example['filename']}")

            # Extract the parsed structure
            parsed = real_example.get("parsed", {})

            # Generate variations
            variations = self._generate_variations(parsed, variations_per_example)

            self.synthetic_examples.extend(variations)
            print(f"      Generated {len(variations)} variations (total: {len(self.synthetic_examples)})")

            # Stop if we've reached target
            if len(self.synthetic_examples) >= self.target_count:
                print(f"\n Reached target of {self.target_count} synthetic examples")
                break

        return len(self.synthetic_examples)

    def _generate_variations(self, parsed_data: Dict, count: int) -> List[Dict]:
        """Generate variations of a single parsed example"""
        variations = []

        # Create prompt for Claude
        prompt = f"""
You are a resume data generator. Given this parsed resume data, generate {count} realistic variations.

ORIGINAL PARSED DATA:
```json
{json.dumps(parsed_data, indent=2)}
```

Generate variations by:
1. Keeping the structure intact
2. Varying names, companies, skills, etc. realistically
3. Maintaining realistic date ranges and career progression
4. Creating diverse roles and skill combinations

Return as JSON array where each element is a complete parsed_data object with these fields:
- full_name: Person's name
- email: Email address
- phone: Phone number
- current_title: Current job title
- current_employer: Current employer
- work_history: Array of jobs
- education: Array of education entries
- skills: Array of skill strings
- certifications: Array of certs
- languages: Array of languages

IMPORTANT:
- Return ONLY valid JSON array, no other text
- Each name should be unique and realistic
- Each email should be unique
- Maintain realistic career progression (dates make sense)
- Skills should match the roles
- All entries must be realistic

Generate {count} variations now:
```json
"""

        try:
            # Call Claude with streaming for faster responses
            print(f"       Calling Claude API...", end="", flush=True)

            response = client.messages.create(
                model="claude-opus-5",
                max_tokens=8000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = response.content[0].text

            # Parse the JSON response
            print(f" ")
            print(f"       Parsing response...", end="", flush=True)

            # Extract JSON array from response
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1

            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                variation_data = json.loads(json_str)

                # Validate and format
                for i, var in enumerate(variation_data[:count]):
                    if isinstance(var, dict):
                        variations.append({
                            "parsed": var,
                            "source": "synthetic",
                            "generated_from": parsed_data.get('full_name', 'unknown'),
                            "generated_at": datetime.utcnow().isoformat()
                        })

                print(f"  Parsed {len(variations)} valid entries")
            else:
                print(f"   Could not parse JSON response")

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            print(f"  Error: {e}")

        return variations

    def validate_synthetic_data(self) -> Dict:
        """Validate quality of synthetic data"""
        print(f"\n Validating {len(self.synthetic_examples)} synthetic examples...")

        validation_issues = []
        field_coverage = {
            "full_name": 0,
            "email": 0,
            "phone": 0,
            "current_title": 0,
            "work_history": 0,
            "education": 0,
            "skills": 0,
        }

        for example in self.synthetic_examples:
            parsed = example.get("parsed", {})

            # Check required fields
            if not parsed.get("full_name"):
                validation_issues.append("Missing full_name")
            else:
                field_coverage["full_name"] += 1

            if not parsed.get("current_title"):
                validation_issues.append("Missing current_title")
            else:
                field_coverage["current_title"] += 1

            if not parsed.get("work_history"):
                validation_issues.append("Missing work_history")
            else:
                field_coverage["work_history"] += 1

            if not parsed.get("skills"):
                validation_issues.append("Missing skills")
            else:
                field_coverage["skills"] += 1

        # Calculate coverage
        total = len(self.synthetic_examples)
        coverage = {field: round(100 * count / total, 1) for field, count in field_coverage.items()}

        return {
            "total_synthetic": total,
            "validation_issues": len(validation_issues),
            "field_coverage": coverage,
            "quality_score": round(100 * (1 - len(validation_issues) / max(1, total)), 1)
        }

    def save_synthetic_data(self):
        """Save synthetic data to file"""
        output_data = {
            "generated_at": datetime.utcnow().isoformat(),
            "total_synthetic": len(self.synthetic_examples),
            "total_real": len(self.real_examples),
            "examples": self.synthetic_examples,
            "validation": self.validate_synthetic_data()
        }

        with open(self.output_file, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"\n Saved synthetic data: {self.output_file}")
        print(f"   Total examples: {len(self.synthetic_examples)}")

        # Print validation
        validation = output_data["validation"]
        print(f"   Quality score: {validation['quality_score']}%")
        print(f"   Field coverage:")
        for field, coverage in validation["field_coverage"].items():
            print(f"     - {field}: {coverage}%")

    def run(self):
        """Run complete generation pipeline"""
        print("\n" + "=" * 70)
        print("SYNTHETIC TRAINING DATA GENERATION")
        print("=" * 70)

        # Load
        real_count = self.load_real_examples()

        if real_count == 0:
            print(" No real examples to generate from")
            return False

        # Generate
        self.generate_synthetic_data()

        if not self.synthetic_examples:
            print(" Failed to generate synthetic data")
            return False

        # Save
        self.save_synthetic_data()

        print(f"\n Generation complete!")
        print(f"   Real: {real_count}")
        print(f"   Synthetic: {len(self.synthetic_examples)}")
        print(f"   Combined: {real_count + len(self.synthetic_examples)}")

        print(f"\n Next step:")
        print(f"   python fine_tune_bert.py --training-data {self.input_file} --synthetic-data {self.output_file}")

        return True


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic training examples using Claude"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input file with real training examples (JSON)"
    )
    parser.add_argument(
        "--output",
        default="synthetic_data.json",
        help="Output file for synthetic examples"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5000,
        help="Target number of synthetic examples to generate"
    )

    args = parser.parse_args()

    generator = SyntheticDataGenerator(args.input, args.output, args.count)
    success = generator.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

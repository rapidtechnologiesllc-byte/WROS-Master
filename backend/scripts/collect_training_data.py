#!/usr/bin/env python3
"""
Resume Training Data Collection Pipeline

Collects real resumes, extracts with SLM, validates, and prepares for BERT fine-tuning.

Process:
1. Read all resumes from OneDrive folder
2. Parse with current SLM (resume_parser_slm.py)
3. Interactive validation: fix any errors
4. Export as JSON training data
5. Ready for: generate_synthetic_examples.py → fine_tune_bert.py

Usage:
    python collect_training_data.py --resume-dir "/path/to/resumes" --output training_data.json
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
import argparse
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.resume_parser_slm import ResumeSLM
from app.services.resume_parsing_service import extract_text_from_pdf, extract_text_from_docx


class TrainingDataCollector:
    """Collect and validate training examples from real resumes"""

    def __init__(self, resume_dir: str, output_file: str = "training_data.json"):
        self.resume_dir = Path(resume_dir)
        self.output_file = Path(output_file)
        self.examples = []
        self.errors = []

    def collect_from_directory(self, interactive: bool = True) -> Dict:
        """
        Collect training data from all resumes in directory.

        Args:
            interactive: If True, prompt to validate/correct each extraction
        """
        if not self.resume_dir.exists():
            raise ValueError(f"Resume directory not found: {self.resume_dir}")

        # Find all resume files
        resume_files = list(self.resume_dir.glob("**/*.pdf")) + \
                      list(self.resume_dir.glob("**/*.docx")) + \
                      list(self.resume_dir.glob("**/*.doc"))

        if not resume_files:
            print(f"No resume files found in {self.resume_dir}")
            return {"status": "error", "message": "No files found"}

        print(f"\n📄 Found {len(resume_files)} resume files")
        print("=" * 70)

        for i, resume_file in enumerate(resume_files, 1):
            print(f"\n[{i}/{len(resume_files)}] Processing: {resume_file.name}")
            self._process_resume(resume_file, interactive=interactive)

        summary = self._generate_summary()
        self._save_training_data(summary)

        return summary

    def _process_resume(self, resume_file: Path, interactive: bool = True):
        """Process a single resume file"""
        try:
            # Extract text
            print(f"  → Extracting text...", end="", flush=True)
            raw_text = self._extract_text(resume_file)
            print(f" ✓ ({len(raw_text)} chars)")

            if not raw_text or len(raw_text) < 100:
                print(f"  ⚠️  Text too short ({len(raw_text)} chars), skipping")
                self.errors.append({
                    "file": resume_file.name,
                    "error": "text_too_short"
                })
                return

            # Parse with SLM
            print(f"  → Parsing with SLM...", end="", flush=True)
            parsed = ResumeSLM.parse_resume(raw_text)
            print(f" ✓")

            # Validate/correct
            if interactive:
                validated = self._interactive_validation(resume_file, parsed, raw_text)
            else:
                validated = parsed

            # Add to training set
            example = {
                "filename": resume_file.name,
                "raw_text": raw_text[:2000],  # Limit raw text for storage
                "parsed": validated,
                "parsed_at": datetime.utcnow().isoformat(),
                "confidence_scores": self._estimate_confidence(parsed, validated),
            }

            self.examples.append(example)
            print(f"  ✅ Added to training set ({len(self.examples)} total)")

        except Exception as e:
            print(f" ❌ Error: {e}")
            self.errors.append({
                "file": resume_file.name,
                "error": str(e)
            })

    def _extract_text(self, resume_file: Path) -> str:
        """Extract text from resume file"""
        suffix = resume_file.suffix.lower()

        with open(resume_file, 'rb') as f:
            content = f.read()

        if suffix == '.pdf':
            return extract_text_from_pdf(content)
        elif suffix in ['.docx', '.doc']:
            return extract_text_from_docx(content)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

    def _interactive_validation(self, resume_file: Path, parsed: Dict, raw_text: str) -> Dict:
        """
        Interactively validate and correct parsed data.

        User can review and fix extractions before adding to training set.
        """
        print(f"\n  📋 Review extraction results:")
        print(f"     Name: {parsed.get('full_name') or '(empty)'}")
        print(f"     Title: {parsed.get('current_title') or '(empty)'}")
        print(f"     Employer: {parsed.get('current_employer') or '(empty)'}")
        print(f"     Skills: {len(parsed.get('skills') or [])} found")
        print(f"     Jobs: {len(parsed.get('work_history') or [])} found")
        print(f"     Education: {len(parsed.get('education') or [])} found")

        # Allow corrections
        response = input("\n     Accept? (y/n/edit): ").strip().lower()

        if response == 'n':
            print("     Skipping this resume")
            return None

        if response == 'edit':
            return self._edit_extraction(parsed)

        return parsed

    def _edit_extraction(self, parsed: Dict) -> Dict:
        """Allow editing individual fields"""
        while True:
            print("\n  Edit fields:")
            print("    1. full_name")
            print("    2. current_title")
            print("    3. current_employer")
            print("    4. skills (comma-separated)")
            print("    5. Done editing")

            choice = input("  Select field (1-5): ").strip()

            if choice == '1':
                parsed['full_name'] = input(f"    Current: {parsed.get('full_name')}\n    New: ").strip() or parsed.get('full_name')
            elif choice == '2':
                parsed['current_title'] = input(f"    Current: {parsed.get('current_title')}\n    New: ").strip() or parsed.get('current_title')
            elif choice == '3':
                parsed['current_employer'] = input(f"    Current: {parsed.get('current_employer')}\n    New: ").strip() or parsed.get('current_employer')
            elif choice == '4':
                skills_input = input(f"    Current: {', '.join(parsed.get('skills') or [])}\n    New (comma-separated): ").strip()
                if skills_input:
                    parsed['skills'] = [s.strip() for s in skills_input.split(',')]
            elif choice == '5':
                break
            else:
                print("    Invalid choice")

        return parsed

    def _estimate_confidence(self, parsed: Dict, validated: Dict) -> Dict:
        """Estimate confidence scores for each field"""
        confidence = {}

        for field in ['full_name', 'email', 'phone', 'current_title', 'current_employer']:
            if parsed.get(field) == validated.get(field):
                # Unchanged = higher confidence
                confidence[field] = 0.9 if field in ['full_name', 'email', 'phone'] else 0.7
            else:
                # Changed = needs more training
                confidence[field] = 0.5

        # Skills and jobs are harder to get right
        confidence['skills'] = 0.6
        confidence['work_history'] = 0.5
        confidence['education'] = 0.7

        return confidence

    def _generate_summary(self) -> Dict:
        """Generate summary of collected training data"""
        return {
            "status": "completed",
            "total_collected": len(self.examples),
            "total_errors": len(self.errors),
            "fields_covered": {
                "full_name": sum(1 for e in self.examples if e['parsed'].get('full_name')),
                "current_title": sum(1 for e in self.examples if e['parsed'].get('current_title')),
                "current_employer": sum(1 for e in self.examples if e['parsed'].get('current_employer')),
                "work_history": sum(1 for e in self.examples if e['parsed'].get('work_history')),
                "education": sum(1 for e in self.examples if e['parsed'].get('education')),
                "skills": sum(1 for e in self.examples if e['parsed'].get('skills')),
            },
            "output_file": str(self.output_file),
            "next_steps": [
                "python generate_synthetic_examples.py --input training_data.json --output synthetic_data.json --count 5000",
                "python fine_tune_bert.py --training-data training_data.json --synthetic-data synthetic_data.json --output models/resume_parser_bert"
            ]
        }

    def _save_training_data(self, summary: Dict):
        """Save collected training data to JSON"""
        output_data = {
            "collected_at": datetime.utcnow().isoformat(),
            "total_examples": len(self.examples),
            "examples": self.examples,
            "summary": {k: v for k, v in summary.items() if k != "next_steps"}
        }

        with open(self.output_file, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"\n✅ Training data saved: {self.output_file}")
        print(f"   Total examples: {len(self.examples)}")
        print(f"   Errors: {len(self.errors)}")

        # Print next steps
        print(f"\n📋 Next steps:")
        for step in summary.get("next_steps", []):
            print(f"   {step}")


def main():
    parser = argparse.ArgumentParser(
        description="Collect resume training data from directory"
    )
    parser.add_argument(
        "--resume-dir",
        required=True,
        help="Directory containing resume files (PDF/DOCX)"
    )
    parser.add_argument(
        "--output",
        default="training_data.json",
        help="Output JSON file for training data"
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Skip interactive validation (use parsed values as-is)"
    )

    args = parser.parse_args()

    collector = TrainingDataCollector(args.resume_dir, args.output)
    summary = collector.collect_from_directory(interactive=not args.no_interactive)

    print(f"\n" + "=" * 70)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

// Client-side resume text extraction and light heuristic field inference (PDF / DOCX).

const EMAIL_RE = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/;

const PHONE_RES = [
  /\+\d{1,3}[\s.-]?\d{2,4}[\s.-]?\d{2,4}[\s.-]?\d{2,9}/,
  /\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}/,
  /\d{3}[\s.-]\d{3}[\s.-]\d{4}/
];

function normalizePhone(raw) {
  const digits = String(raw).replace(/[^\d]/g, "");
  // Typical phone digit count: 10 to 15 (includes country code).
  if (digits.length < 10 || digits.length > 15) return "";
  return String(raw).replace(/\s+/g, " ").trim();
}

function guessMobile(text) {
  for (const re of PHONE_RES) {
    const m = text.match(re);
    if (m) {
      const normalized = normalizePhone(m[0]);
      if (normalized) return normalized;
    }
  }

  // Fallback: broader "digit heavy" substring for cases like "Phone: 555 123 4567".
  const anyNumberish = text.match(/(\+?\d[\d\s().-]{8,}\d)/);
  if (!anyNumberish) return "";

  return normalizePhone(anyNumberish[1]) || "";
}

function splitFullName(full) {
  const parts = full
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((p) => p.replace(/\s+/g, " "));
  if (parts.length === 0) return {};
  if (parts.length === 1) return { firstName: parts[0] };
  if (parts.length === 2) return { firstName: parts[0], lastName: parts[1] };
  return {
    firstName: parts[0],
    middleName: parts.slice(1, -1).join(" "),
    lastName: parts[parts.length - 1]
  };
}

function guessNameLine(lines, emailInText) {
  const beforeEmail = emailInText
    ? lines.slice(
        0,
        Math.max(
          0,
          lines.findIndex((l) => EMAIL_RE.test(l)) === -1
            ? 6
            : lines.findIndex((l) => EMAIL_RE.test(l))
        )
      )
    : lines.slice(0, 8);

  const skip = /^(resume|cv|curriculum|phone|email|mobile|linkedin|github|http|summary|objective|education|experience|skills|work)\b/i;

  for (const line of beforeEmail) {
    if (line.length < 3 || line.length > 60) continue;
    if (skip.test(line)) continue;
    if (EMAIL_RE.test(line) || /^\+?\d[\d\s().-]{8,}$/.test(line)) continue;
    if (/^[^A-Za-z]+$/.test(line)) continue;
    const words = line.split(/\s+/).filter(Boolean);
    if (words.length < 2 || words.length > 5) continue;
    if (words.every((w) => /^[A-Z.]+$/.test(w) && w.length <= 2)) continue;
    if (/^[A-Za-z][a-z]+(?:\s+[A-Za-z][a-z]+)+(?:\s+[A-Za-z][a-z]+)*$/.test(line))
      return line;
    if (/^[A-Z][A-Z\s.'-]+$/.test(line) && words.length >= 2 && words.length <= 4)
      return line
        .toLowerCase()
        .replace(/\b\w/g, (c) => c.toUpperCase());
  }

  // Fallback: pick the first "reasonable" line near the top that looks like a name.
  const fallbackCandidates = beforeEmail.filter((line) => {
    if (skip.test(line)) return false;
    if (EMAIL_RE.test(line)) return false;
    if (/\d/.test(line)) return false;
    const words = line.split(/\s+/).filter(Boolean);
    if (words.length < 2 || words.length > 5) return false;
    const alphaWords = words.filter((w) => /[A-Za-z]/.test(w));
    if (alphaWords.length < 2) return false;
    if (alphaWords.some((w) => w.length > 22)) return false;
    return true;
  });

  if (!fallbackCandidates.length) return "";

  const candidate = fallbackCandidates[0].replace(/[,:;]+$/g, "").trim();
  // If it's fully lowercase/mixed, title-case it.
  if (!/[A-Z]{2,}/.test(candidate) && candidate === candidate.toLowerCase()) {
    return candidate
      .split(/\s+/)
      .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
      .join(" ");
  }

  return candidate;
}

function extractSkillsBlob(text) {
  const m = text.match(
    /(?:^|\n)\s*(?:technical\s+)?skills\s*:?\s*([\s\S]+?)(?=\n\s*(?:experience|work\s+history|education|employment|projects|certifications)\b|\n{2,}|$)/i
  );
  if (m) {
    return m[1]
      .split(/\n/)
      .map((l) => l.trim())
      .filter((l) => l && !/^(skills|technical)/i.test(l))
      .join(", ")
      .replace(/\s*,\s*/g, ", ")
      .trim();
  }

  // Fallback: match common tech keywords even when resume lacks "Skills" heading.
  const knownSkills = [
    "JavaScript",
    "TypeScript",
    "React",
    "Node.js",
    "Express",
    "Java",
    "Python",
    "C#",
    "SQL",
    "MySQL",
    "PostgreSQL",
    "MongoDB",
    "HTML",
    "CSS",
    "Tailwind",
    "Redux",
    "Next.js",
    "AWS",
    "Azure",
    "Docker",
    "Kubernetes",
    "Git",
    "Jenkins",
    "REST API",
    "GraphQL",
    "Spring Boot",
    "Microservices"
  ];

  const found = [];
  const lowerText = text.toLowerCase();
  for (const skill of knownSkills) {
    if (lowerText.includes(skill.toLowerCase())) found.push(skill);
  }
  return found.join(", ");
}

function guessExperience(text) {
  const normalized = text.replace(/\s+/g, " ");
  const yearsLabel = normalized.match(
    /(?:total\s+)?(?:overall\s+)?(?:professional\s+)?(?:work\s+)?(?:experience|exp\.?)\s*:?\s*(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)/i
  );
  if (yearsLabel) return `${yearsLabel[1]} years`;

  const yearsInline = normalized.match(
    /(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?\.?)\s+(?:of\s+)?(?:experience|exp\.?|in\s+development)/i
  );
  if (yearsInline) return `${yearsInline[1]} years`;

  const range = text.match(
    /(\d{4})\s*[-–]\s*(?:present|\d{4})/i
  );
  if (range) return `Since ${range[1]}`;
  return "";
}

function guessLocation(text) {
  const labeled = text.match(
    /(?:^|\n)\s*(?:location|address|based\s+in)\s*:?\s*([^\n]+)/i
  );
  if (labeled) return labeled[1].trim().slice(0, 120);
  const cityState = text.match(
    /\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s*([A-Z]{2})\b/
  );
  if (cityState) return `${cityState[1]}, ${cityState[2]}`;
  return "";
}

/**
 * @param {string} raw
 * @returns {Record<string, string>}
 */
export function inferFieldsFromResumeText(raw) {
  const text = raw.replace(/\r/g, "\n");
  const lines = text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);

  const out = {};

  const emailMatch = text.match(EMAIL_RE);
  if (emailMatch) out.email = emailMatch[0];

  const mobile = guessMobile(text);
  if (mobile) out.mobile = mobile;

  const nameLine = guessNameLine(lines, !!emailMatch);
  if (nameLine) Object.assign(out, splitFullName(nameLine));

  const skills = extractSkillsBlob(text);
  if (skills) out.skills = skills.replace(/^[, ]+|[, ]+$/g, "");

  const experience = guessExperience(text);
  if (experience) out.experience = experience;

  const location = guessLocation(text);
  if (location) out.currentLocation = location;

  return out;
}

/**
 * @param {File} file
 * @returns {Promise<string>}
 */
export async function extractResumeText(file) {
  const name = (file.name || "").toLowerCase();
  const type = file.type || "";

  if (type === "application/pdf" || name.endsWith(".pdf")) {
    const pdfjs = await import("pdfjs-dist");
    pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.mjs`;
    const data = new Uint8Array(await file.arrayBuffer());
    const pdf = await pdfjs.getDocument({ data }).promise;
    const parts = [];
    for (let i = 1; i <= pdf.numPages; i++) {
      const page = await pdf.getPage(i);
      const content = await page.getTextContent();
      const line = content.items.map((item) => item.str).join(" ");
      parts.push(line);
    }
    return parts.join("\n");
  }

  if (
    type ===
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
    name.endsWith(".docx")
  ) {
    const mammothMod = await import("mammoth");
    const mammoth = mammothMod.default || mammothMod;
    const result = await mammoth.extractRawText({
      arrayBuffer: await file.arrayBuffer()
    });
    return (result && result.value) || "";
  }

  if (name.endsWith(".doc") && type !== "application/pdf") {
    throw new Error(
      "Auto-fill supports PDF and DOCX. Save as DOCX or PDF, or fill the form manually."
    );
  }

  throw new Error("Unsupported file type for auto-fill. Use PDF or DOCX.");
}

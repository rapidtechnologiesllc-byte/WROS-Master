// Boolean search over every candidate you may see (open requirements P903/P908/P911/P902, CEO 2026-11-16): skills,
// titles and resumes, with where each word matched, how many each word finds and how to change a search that finds
// nothing or too much; your saved searches (when and how many each last found) and the team's skill synonyms.
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card, Button, Input, TextArea, Table } from "../components/ui";
import { BooleanSearchHelp, FoundWhere, SearchExplain } from "../components/BooleanSearchHelp";
import {
  deleteSavedSearch, deleteSkillSynonym, listSavedSearches, listSkillSynonyms, saveSearch, saveSkillSynonym,
  searchCandidates,
} from "../services/api/jobSearch";
import { hasPermission } from "../utils/permissionsRoleTemplate";

const when = (value) => (value ? new Date(value).toLocaleString() : "never");

function SynonymLibrary() {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("");
  const [skill, setSkill] = useState("");
  const [names, setNames] = useState("");
  const [error, setError] = useState("");
  const canEdit = hasPermission("candidates", "edit");

  const load = useCallback(async () => {
    try {
      setItems(await listSkillSynonyms());
    } catch (err) {
      setError(`Couldn't load the synonyms: ${err.message}`);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const edit = (item) => {
    setSkill(item.skill);
    setNames(item.added.join(", "));
  };

  const save = async () => {
    setError("");
    try {
      await saveSkillSynonym(skill, names.split(",").map((n) => n.trim()).filter(Boolean));
      setSkill("");
      setNames("");
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const remove = async (item) => {
    setError("");
    try {
      await deleteSkillSynonym(item.skill);
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const shown = items.filter((i) => !filter || `${i.skill} ${i.other_names.join(" ")}`.toLowerCase().includes(filter.toLowerCase()));
  return (
    <div className="space-y-3">
      <div className="text-xs text-gray-600">
        Searching a skill also finds every other name it goes by. The platform's names are fixed; your team can add more.
      </div>
      {error ? <div className="text-xs text-rose-700">{error}</div> : null}
      {canEdit ? (
        <div className="grid grid-cols-1 items-end gap-2 sm:grid-cols-[14rem_1fr_auto]">
          <Input label="Skill" value={skill} onChange={setSkill} placeholder="PolicyCenter (one word)" />
          <Input label="Other names it goes by (comma separated)" value={names} onChange={setNames} placeholder="PC, Policy Center" />
          <Button onClick={save} disabled={!skill.trim() || !names.trim()}>Save names</Button>
        </div>
      ) : null}
      <Input label="Find a skill" value={filter} onChange={setFilter} placeholder="guidewire" />
      <Table
        columns={[
          { key: "skill", header: "Skill" },
          { key: "builtIn", header: "Platform names" },
          { key: "added", header: "Added by your team" },
          { key: "actions", header: "" },
        ]}
        rows={shown.map((item) => ({
          id: item.skill,
          skill: <span className="font-semibold">{item.skill}</span>,
          builtIn: item.built_in.join(", ") || "—",
          added: item.added.length ? (
            <div>
              <div>{item.added.join(", ")}</div>
              <div className="text-xs text-gray-500">{item.updated_by_name ? `by ${item.updated_by_name}` : ""}</div>
            </div>
          ) : "—",
          actions: canEdit ? (
            <div className="flex gap-1">
              <Button variant="ghost" onClick={() => edit(item)}>{item.added.length ? "Edit" : "Add names"}</Button>
              {item.added.length ? <Button variant="ghost" onClick={() => remove(item)}>Remove added</Button> : null}
            </div>
          ) : null,
        }))}
      />
    </div>
  );
}

export default function CandidateBooleanSearch() {
  const [query, setQuery] = useState("");
  const [minYears, setMinYears] = useState("");
  const [location, setLocation] = useState("");
  const [result, setResult] = useState(null);
  const [saved, setSaved] = useState([]);
  const [saveName, setSaveName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [showSynonyms, setShowSynonyms] = useState(false);

  const loadSaved = useCallback(async () => {
    try {
      setSaved(await listSavedSearches());
    } catch (err) {
      setError(`Couldn't load your saved searches: ${err.message}`);
    }
  }, []);

  useEffect(() => {
    loadSaved();
  }, [loadSaved]);

  const run = async (search = { q: query, minExperienceYears: minYears, location }) => {
    if (!search.q.trim()) {
      setError("Type what to search for.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      setResult(await searchCandidates(search));
      if (search.savedId) loadSaved();
    } catch (err) {
      setResult(null);
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const runSaved = (s) => {
    setQuery(s.query);
    setMinYears(s.min_experience_years ?? "");
    setLocation(s.location || "");
    setSaveName(s.name);
    run({ q: s.query, minExperienceYears: s.min_experience_years ?? "", location: s.location || "", savedId: s.id });
  };

  const keep = async () => {
    setError("");
    try {
      await saveSearch({
        name: saveName.trim(), query: query.trim(), location: location.trim() || null,
        min_experience_years: minYears === "" ? null : parseFloat(minYears),
      });
      loadSaved();
    } catch (err) {
      setError(err.message);
    }
  };

  const forget = async (s) => {
    try {
      await deleteSavedSearch(s.id);
      loadSaved();
    } catch (err) {
      setError(err.message);
    }
  };

  const rows = (result?.results || []).map((r) => ({
    id: r.candidate_id,
    name: <Link className="font-semibold text-blue-600 hover:underline" to={`/candidates/${r.candidate_id}`}>{r.name}</Link>,
    title: r.title || "—",
    location: r.location || "—",
    experience: r.experience_years != null ? `${r.experience_years} yrs` : "—",
    score: r.score,
    found: (
      <div>
        <FoundWhere found={r.found} />
        {r.snippet ? <div className="mt-1 max-w-md text-xs italic text-gray-500">{r.snippet}</div> : null}
      </div>
    ),
  }));

  return (
    <div className="space-y-4">
      <Card title="Boolean search" subtitle="Search every candidate you can see by their skills, title and resume.">
        {error ? <div className="mb-3 text-xs text-rose-700">{error}</div> : null}
        <div className="space-y-3">
          <TextArea label="Search" value={query} onChange={setQuery} rows={2} />
          <BooleanSearchHelp />
          <div className="grid grid-cols-1 items-end gap-3 sm:grid-cols-[10rem_14rem_auto]">
            <Input label="Experience at least (years)" value={minYears} onChange={setMinYears} placeholder="5" />
            <Input label="Location contains" value={location} onChange={setLocation} placeholder="Dallas" />
            <Button onClick={() => run()} disabled={busy}>{busy ? "Searching…" : "Search"}</Button>
          </div>
          {result ? (
            <>
              <div className="text-sm text-gray-700">
                <span className="font-semibold">{result.total}</span> of {result.searched} candidates match{" "}
                <code className="rounded bg-gray-100 px-1">{result.query}</code>
                {result.total > rows.length ? ` (showing the best ${rows.length})` : ""}
              </div>
              <SearchExplain result={result} />
              <div className="flex flex-wrap items-end gap-2">
                <Input label="Save this search as" value={saveName} onChange={setSaveName} placeholder="PolicyCenter devs, Dallas" />
                <Button variant="secondary" onClick={keep} disabled={!saveName.trim() || !query.trim()}>Save search</Button>
              </div>
              <Table
                columns={[
                  { key: "name", header: "Candidate" },
                  { key: "title", header: "Title" },
                  { key: "location", header: "Location" },
                  { key: "experience", header: "Experience" },
                  { key: "score", header: "Score" },
                  { key: "found", header: "Where it matched" },
                ]}
                rows={rows}
              />
            </>
          ) : null}
        </div>
      </Card>

      <Card title="Your saved searches" subtitle="Run one again; each shows when it last ran and how many it found.">
        {saved.length ? (
          <Table
            columns={[
              { key: "name", header: "Name" },
              { key: "query", header: "Search" },
              { key: "last", header: "Last run" },
              { key: "actions", header: "" },
            ]}
            rows={saved.map((s) => ({
              id: s.id,
              name: <span className="font-semibold">{s.name}</span>,
              query: (
                <div className="text-xs">
                  <code className="rounded bg-gray-100 px-1">{s.query}</code>
                  {s.min_experience_years != null ? ` · ${s.min_experience_years}+ yrs` : ""}
                  {s.location ? ` · ${s.location}` : ""}
                </div>
              ),
              last: <span className="text-xs">{when(s.last_run_at)}{s.last_result_count != null ? ` · ${s.last_result_count} found` : ""}</span>,
              actions: (
                <div className="flex gap-1">
                  <Button variant="ghost" onClick={() => runSaved(s)}>Run</Button>
                  <Button variant="ghost" onClick={() => forget(s)}>Remove</Button>
                </div>
              ),
            }))}
          />
        ) : (
          <div className="text-sm text-gray-500">None yet: run a search and save it.</div>
        )}
      </Card>

      <Card
        title="Skill synonyms"
        subtitle="The other names each skill goes by, used by every search."
        right={<Button variant="ghost" onClick={() => setShowSynonyms((v) => !v)}>{showSynonyms ? "Hide" : "Show"}</Button>}
      >
        {showSynonyms ? <SynonymLibrary /> : <div className="text-sm text-gray-500">Show the list to see or add names.</div>}
      </Card>
    </div>
  );
}

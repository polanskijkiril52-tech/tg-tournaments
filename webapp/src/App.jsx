import React, { useEffect, useMemo, useState } from "react";

const tg = window.Telegram?.WebApp ?? null;
const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
const cx = (...a) => a.filter(Boolean).join(" ");

function useTelegramTheme() {
  const [theme, setTheme] = useState(() => tg?.themeParams || {});
  useEffect(() => {
    if (!tg) return;
    tg.ready?.();
    tg.expand?.();
    const handler = () => setTheme(tg.themeParams || {});
    tg.onEvent("themeChanged", handler);
    return () => tg.offEvent("themeChanged", handler);
  }, []);
  return theme;
}

function Pill({ children, tone = "neutral" }) {
  return <span className={cx("pill", `pill--${tone}`)}>{children}</span>;
}
function LinkButton({ href, children }) {
  if (!href) return null;
  return <a className={cx("btn", "btn--secondary")} href={href} target="_blank" rel="noreferrer">{children}</a>;
}
function SteamSummary({ user }) {
  if (!user?.steam_profile_url) return <div className="muted">Можно указать Steam ID64, vanity или полную ссылку на профиль.</div>;
  return (
    <div className="stack" style={{ gap: 8 }}>
      <div className="row" style={{ alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        {user.steam_avatar_url ? <img src={user.steam_avatar_url} alt="Steam avatar" style={{ width: 48, height: 48, borderRadius: 999, objectFit: "cover", border: "1px solid rgba(255,255,255,.12)" }} /> : null}
        <div>
          <div><b>{user.steam_display_name || user.steam_account_label || "Steam profile"}</b></div>
          <div className="muted">{user.steam_account_label || user.steam_profile_url}</div>
        </div>
      </div>
      <div className="row" style={{ flexWrap: "wrap" }}>
        <LinkButton href={user.steam_profile_url}>Открыть Steam</LinkButton>
        <LinkButton href={user.dotabuff_url}>Dotabuff</LinkButton>
        <LinkButton href={user.opendota_url}>OpenDota</LinkButton>
      </div>
    </div>
  );
}
function Card({ children }) { return <div className="card">{children}</div>; }
function Button({ children, variant = "primary", ...props }) {
  return <button className={cx("btn", `btn--${variant}`)} {...props}>{children}</button>;
}

function buildHeaders(token, json = false) {
  const h = {};
  if (json) h["Content-Type"] = "application/json";
  if (token) h.Authorization = `Bearer ${token}`;
  if (tg?.initData) h["X-Init-Data"] = tg.initData;
  return h;
}
async function api(path, method = "GET", body, token) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: buildHeaders(token, body !== undefined),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
  return data;
}

function prettyStatus(s) {
  return ({ open: "open", running: "running", finished: "finished", pending: "pending", ready: "ready", disputed: "disputed", registration: "registration", draft: "draft" })[s] || s;
}
function statusTone(s) {
  if (s === "open") return "green";
  if (s === "running" || s === "ready") return "orange";
  if (s === "finished") return "blue";
  return "neutral";
}
function groupLabel(g) { return ({ WB: "Upper", LB: "Lower", GF: "Grand Final" })[g] || g; }
function bracketLabel(b) { return b === "double" ? "double elimination" : "single elimination"; }

function BracketVisual({ bracket, myTeamId, onOpenMatch }) {
  const matchList = Object.values(bracket?.rounds || {}).flat();
  if (!matchList.length) return <div className="muted">Сетка появится после старта турнира.</div>;
  const groups = ["WB", "LB", "GF"];
  return (
    <div className="stack" style={{ gap: 14 }}>
      {groups.map((group) => {
        const rounds = [...new Set(matchList.filter((m) => m.bracket_group === group).map((m) => m.round))].sort((a, b) => a - b);
        if (!rounds.length) return null;
        return (
          <div key={group}>
            <div className="sectionTitle">{groupLabel(group)}</div>
            <div className="bracketScroller">
              <div className="bracketCols">
                {rounds.map((round) => {
                  const items = matchList
                    .filter((m) => m.bracket_group === group && m.round === round)
                    .sort((a, b) => (a.position || 0) - (b.position || 0));
                  return (
                    <div className="bracketCol" key={`${group}-${round}`}>
                      <div className="bracketColTitle">Раунд {round}</div>
                      {items.map((m) => {
                        const mine = myTeamId && (m.team1?.id === myTeamId || m.team2?.id === myTeamId);
                        return (
                          <button key={m.id} className={cx("bracketMatch", mine && "bracketMatch--mine")} onClick={() => onOpenMatch(m.id)}>
                            <div className="bracketTeam">{m.team1?.name || "TBD"}{m.winner?.id === m.team1?.id ? " ✓" : ""}</div>
                            <div className="bracketDivider" />
                            <div className="bracketTeam">{m.team2?.name || "TBD"}{m.winner?.id === m.team2?.id ? " ✓" : ""}</div>
                            <div className="bracketMeta">
                              <span>{prettyStatus(m.status)}</span>
                              {mine ? <span>ваш матч</span> : null}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function App() {
  const theme = useTelegramTheme();
  const [screen, setScreen] = useState("tournaments");
  const [selectedTournamentId, setSelectedTournamentId] = useState(null);
  const [selectedMatchId, setSelectedMatchId] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem("token") || "");
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState("");

  const [me, setMe] = useState(null);
  const [myTeam, setMyTeam] = useState(null);
  const [tournaments, setTournaments] = useState([]);
  const [bracket, setBracket] = useState(null);
  const [match, setMatch] = useState(null);
  const [nextMatch, setNextMatch] = useState(null);
  const [history, setHistory] = useState([]);
  const [adminOverview, setAdminOverview] = useState(null);

  const [regUsername, setRegUsername] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [devLoginName, setDevLoginName] = useState("testuser");

  const [teamName, setTeamName] = useState("");
  const [joinCode, setJoinCode] = useState("");

  const [profileDisplayName, setProfileDisplayName] = useState("");
  const [profileBio, setProfileBio] = useState("");
  const [profileRole, setProfileRole] = useState("");
  const [profileSteam, setProfileSteam] = useState("");

  const [tTitle, setTTitle] = useState("");
  const [tFormat, setTFormat] = useState("5v5");
  const [tMaxTeams, setTMaxTeams] = useState(8);
  const [tStartAt, setTStartAt] = useState("");
  const [tBracketType, setTBracketType] = useState("single");
  const [tRulesText, setTRulesText] = useState("");

  const [score1, setScore1] = useState(0);
  const [score2, setScore2] = useState(0);
  const [proofUrl, setProofUrl] = useState("");

  const isAdmin = !!me?.is_admin;

  const styles = useMemo(() => ({
    "--bg": theme.bg_color || "#07111f",
    "--text": theme.text_color || "#fff",
    "--muted": theme.hint_color || "rgba(255,255,255,.68)",
    "--panel": theme.secondary_bg_color || "rgba(255,255,255,.06)",
    "--primary": theme.button_color || "#2ea6ff",
    "--primaryText": theme.button_text_color || "#fff",
  }), [theme]);

  useEffect(() => { if (token) bootstrap(); else { refreshTournaments(); setMe(null); setMyTeam(null); } }, [token]);
  useEffect(() => { if (me) { setProfileDisplayName(me.display_name || ""); setProfileBio(me.bio || ""); setProfileRole(me.preferred_role || ""); setProfileSteam(me.steam_profile_url || me.steam_account_label || ""); } }, [me]);

  async function bootstrap() {
    await Promise.allSettled([refreshMe(), refreshMyTeam(), refreshTournaments(), refreshNextMatch(), refreshHistory(), refreshAdminOverview()]);
  }
  async function refreshMe() { try { setMe(await api("/me", "GET", undefined, token)); } catch { setMe(null); } }
  async function refreshMyTeam() { try { setMyTeam(await api("/teams/me", "GET", undefined, token)); } catch { setMyTeam(null); } }
  async function refreshTournaments() { try { setTournaments(await api("/tournaments")); } catch {} }
  async function refreshNextMatch() { try { setNextMatch(await api("/matches/next", "GET", undefined, token)); } catch { setNextMatch(null); } }
  async function refreshHistory() { if (!token) return setHistory([]); try { setHistory(await api("/matches/history", "GET", undefined, token)); } catch { setHistory([]); } }
  async function refreshAdminOverview() { if (!token) return setAdminOverview(null); try { setAdminOverview(await api("/admin/overview", "GET", undefined, token)); } catch { setAdminOverview(null); } }

  async function telegramAutoLogin() {
    setLoading(true); setToast("");
    try {
      const data = await api("/auth/telegram", "POST", {}, token);
      localStorage.setItem("token", data.access_token);
      setToken(data.access_token);
      setToast("Вход выполнен");
    } catch (e) { setToast(String(e.message || e)); }
    finally { setLoading(false); }
  }
  async function doDevLogin(name, is_admin = false) {
    setLoading(true); setToast("");
    try {
      const data = await api("/auth/dev-login", "POST", { username: name, is_admin }, token);
      localStorage.setItem("token", data.access_token); setToken(data.access_token); setToast("Тестовый вход выполнен ✅");
    } catch (e) { setToast(String(e.message || e)); } finally { setLoading(false); }
  }
  async function doRegister(e) {
    e.preventDefault(); setLoading(true); setToast("");
    try { const d = await api("/auth/register", "POST", { username: regUsername, password: regPassword }, token); localStorage.setItem("token", d.access_token); setToken(d.access_token); }
    catch (e2) { setToast(String(e2.message || e2)); } finally { setLoading(false); }
  }
  async function doLogin(e) {
    e.preventDefault(); setLoading(true); setToast("");
    try { const d = await api("/auth/login", "POST", { username: loginUsername, password: loginPassword }, token); localStorage.setItem("token", d.access_token); setToken(d.access_token); }
    catch (e2) { setToast(String(e2.message || e2)); } finally { setLoading(false); }
  }
  function logout() { localStorage.removeItem("token"); setToken(""); setScreen("profile"); }

  async function openTournament(id) {
    setSelectedTournamentId(id); setScreen("tournament"); setLoading(true); setToast("");
    try { setBracket(await api(`/tournaments/${id}/bracket`, "GET", undefined, token)); }
    catch (e) { setToast(String(e.message || e)); } finally { setLoading(false); }
  }
  async function openMatch(id) {
    setSelectedMatchId(id); setScreen("match"); setLoading(true); setToast("");
    try { setMatch(await api(`/matches/${id}`, "GET", undefined, token)); }
    catch (e) { setToast(String(e.message || e)); } finally { setLoading(false); }
  }

  async function doCreateTeam(e) {
    e.preventDefault(); setLoading(true); setToast("");
    try { setMyTeam(await api("/teams", "POST", { name: teamName }, token)); setTeamName(""); setToast("Команда создана"); }
    catch (e2) { setToast(String(e2.message || e2)); }
    finally { setLoading(false); }
  }
  async function doJoinByCode(e) {
    e.preventDefault(); setLoading(true); setToast("");
    try { setMyTeam(await api("/teams/join-by-code", "POST", { invite_code: joinCode }, token)); setJoinCode(""); setToast("Вы вступили в команду"); }
    catch (e2) { setToast(String(e2.message || e2)); } finally { setLoading(false); }
  }
  async function doLeaveTeam() {
    if (!window.confirm("Выйти из команды?")) return;
    setLoading(true); setToast("");
    try { await api("/teams/leave", "POST", {}, token); setMyTeam(null); setToast("Вы вышли из команды"); await refreshTournaments(); }
    catch (e) { setToast(String(e.message || e)); } finally { setLoading(false); }
  }
  async function promoteMember(userId) {
    setLoading(true); setToast("");
    try { const data = await api(`/teams/${myTeam.id}/members/${userId}/role`, "POST", { role: "captain" }, token); setMyTeam(data); setToast("Капитан обновлён"); }
    catch (e) { setToast(String(e.message || e)); } finally { setLoading(false); }
  }
  async function kickMember(userId) {
    if (!window.confirm("Удалить игрока из состава?")) return;
    setLoading(true); setToast("");
    try { await api(`/teams/${myTeam.id}/members/${userId}`, "DELETE", undefined, token); await refreshMyTeam(); setToast("Игрок удалён"); }
    catch (e) { setToast(String(e.message || e)); } finally { setLoading(false); }
  }

  async function saveProfile(e) {
    e.preventDefault(); setLoading(true); setToast("");
    try { const data = await api("/me/profile", "PUT", { display_name: profileDisplayName, bio: profileBio, preferred_role: profileRole, steam_account: profileSteam }, token); setMe(data); setToast("Профиль сохранён"); }
    catch (e2) { setToast(String(e2.message || e2)); } finally { setLoading(false); }
  }

  async function doCreateTournament(e) {
    e.preventDefault(); setLoading(true); setToast("");
    try {
      await api("/tournaments", "POST", {
        title: tTitle,
        game: "Dota 2",
        format: tFormat,
        max_teams: tMaxTeams ? Number(tMaxTeams) : null,
        start_at: tStartAt || null,
        bracket_type: tBracketType,
        rules_text: tRulesText || null,
      }, token);
      setTTitle(""); setTRulesText(""); setTStartAt(""); await refreshTournaments(); await refreshAdminOverview(); setToast("Турнир создан"); setScreen("tournaments");
    } catch (e2) { setToast(String(e2.message || e2)); } finally { setLoading(false); }
  }
  async function doJoinTournament() {
    setLoading(true); setToast("");
    try { await api(`/tournaments/${selectedTournamentId}/join`, "POST", { team_id: myTeam.id }, token); await openTournament(selectedTournamentId); setToast("Команда зарегистрирована"); }
    catch (e) { setToast(String(e.message || e)); } finally { setLoading(false); }
  }
  async function doCheckIn() {
    setLoading(true); setToast("");
    try { await api(`/tournaments/${selectedTournamentId}/check-in`, "POST", {}, token); await openTournament(selectedTournamentId); setToast("Check-in обновлён"); }
    catch (e) { setToast(String(e.message || e)); } finally { setLoading(false); }
  }
  async function doStartTournament() {
    setLoading(true); setToast("");
    try { await api(`/tournaments/${selectedTournamentId}/start`, "POST", {}, token); await openTournament(selectedTournamentId); await refreshTournaments(); await refreshNextMatch(); setToast("Турнир стартовал"); }
    catch (e) { setToast(String(e.message || e)); } finally { setLoading(false); }
  }
  async function doDeleteTournament(id, fromDetail = false) {
    if (!window.confirm("Удалить турнир?")) return;
    setLoading(true); setToast("");
    try { await api(`/tournaments/${id}`, "DELETE", undefined, token); await refreshTournaments(); await refreshAdminOverview(); setToast("Турнир удалён"); if (fromDetail) { setBracket(null); setScreen("tournaments"); } }
    catch (e) { setToast(String(e.message || e)); } finally { setLoading(false); }
  }

  async function doReportMatch(e) {
    e.preventDefault(); setLoading(true); setToast("");
    try {
      await api(`/matches/${selectedMatchId}/report`, "POST", { score_team1: Number(score1), score_team2: Number(score2), proof_url: proofUrl || null }, token);
      await openMatch(selectedMatchId); await refreshNextMatch(); await refreshHistory();
      if (selectedTournamentId) await openTournament(selectedTournamentId);
      setToast("Результат отправлен");
    } catch (e2) { setToast(String(e2.message || e2)); } finally { setLoading(false); }
  }
  async function doResolveMatch(teamId) {
    setLoading(true); setToast("");
    try { await api(`/matches/${selectedMatchId}/resolve`, "POST", { winner_team_id: teamId }, token); await openMatch(selectedMatchId); await refreshNextMatch(); await refreshHistory(); if (selectedTournamentId) await openTournament(selectedTournamentId); setToast("Матч завершён админом"); }
    catch (e) { setToast(String(e.message || e)); } finally { setLoading(false); }
  }
  async function doDeleteMatch() {
    if (!window.confirm("Удалить матч?")) return;
    setLoading(true); setToast("");
    try { await api(`/matches/${selectedMatchId}`, "DELETE", undefined, token); setScreen("tournament"); if (selectedTournamentId) await openTournament(selectedTournamentId); setToast("Матч удалён"); }
    catch (e) { setToast(String(e.message || e)); } finally { setLoading(false); }
  }

  const myTeamInTournament = useMemo(() => bracket?.participants?.find((p) => p.team?.id === myTeam?.id), [bracket, myTeam]);
  const myTeamId = myTeam?.id || null;
  const bottomTab = screen === "tournament" || screen === "match" ? "tournaments" : screen;

  return (
    <div className="app" style={styles}>
      <header className="header">
        <div>
          <div className="title">
            {screen === "tournaments" && "Турниры"}
            {screen === "tournament" && (bracket?.tournament?.title || "Турнир")}
            {screen === "match" && "Матч"}
            {screen === "team" && "Моя команда"}
            {screen === "profile" && "Профиль"}
            {screen === "admin" && "Админ-панель"}
          </div>
          <div className="subtitle">Dota 2 • Mini App</div>
        </div>
        {(screen === "tournament" || screen === "match") ? <Button variant="secondary" onClick={() => setScreen(screen === "match" ? "tournament" : "tournaments")}>Назад</Button> : null}
      </header>

      {toast ? <div className="msg">{toast}</div> : null}

      <main className="stack">
        {screen === "tournaments" && (
          <>
            {myTeam ? (
              <Card>
                <div className="cardTitle">Быстрые действия</div>
                <div className="cardHint"><Pill tone="green">команда: {myTeam.name}</Pill> <span className="dot" /> можно регаться в турниры</div>
              </Card>
            ) : null}
            {nextMatch ? (
              <Card>
                <div className="row between">
                  <div>
                    <div className="cardTitle">Мой следующий матч</div>
                    <div className="cardHint"><Pill tone={statusTone(nextMatch.status)}>{prettyStatus(nextMatch.status)}</Pill> <span className="dot" /> {nextMatch.team1?.name} vs {nextMatch.team2?.name}</div>
                  </div>
                  <Button onClick={() => { openTournament(nextMatch.tournament_id).then(() => openMatch(nextMatch.id)); }}>Открыть</Button>
                </div>
              </Card>
            ) : null}
            <Card>
              <div className="row between"><div className="cardTitle">Список турниров</div><Button variant="secondary" onClick={refreshTournaments}>Обновить</Button></div>
              <div className="stack" style={{ marginTop: 10 }}>
                {tournaments.map((t) => (
                  <div className="listItem" key={t.id}>
                    <div className="row between top">
                      <div>
                        <div className="cardTitle" style={{ fontSize: 22 }}>{t.title}</div>
                        <div className="cardHint">
                          <Pill tone="purple">{t.format}</Pill>
                          <span className="dot" />
                          <Pill tone={statusTone(t.status)}>{prettyStatus(t.status)}</Pill>
                          <span className="dot" />
                          <Pill tone="blue">{bracketLabel(t.bracket_type)}</Pill>
                          {t.max_teams ? <><span className="dot" /><span className="muted">макс. команд: {t.max_teams}</span></> : null}
                        </div>
                      </div>
                      <div className="row">
                        {isAdmin ? <Button variant="secondary" onClick={() => doDeleteTournament(t.id)}>Удалить</Button> : null}
                        <Button onClick={() => openTournament(t.id)}>Открыть</Button>
                      </div>
                    </div>
                  </div>
                ))}
                {!tournaments.length ? <div className="muted">Пока нет турниров.</div> : null}
              </div>
            </Card>
          </>
        )}

        {screen === "tournament" && bracket && (
          <>
            <Card>
              <div className="row between top">
                <div>
                  <div className="cardTitle">Инфо</div>
                  <div className="cardHint">
                    <Pill tone={statusTone(bracket.tournament.status)}>{prettyStatus(bracket.tournament.status)}</Pill>
                    <span className="dot" />
                    <Pill tone="blue">{bracketLabel(bracket.tournament.bracket_type)}</Pill>
                    <span className="dot" />
                    <span className="muted">участников: {bracket.participants?.length || 0}</span>
                    {myTeam ? <><span className="dot" /><span className="muted">ваша команда: {myTeam.name}</span></> : null}
                  </div>
                </div>
                <div className="stack actionsCol">
                  {token && myTeam && !myTeamInTournament && ["open","registration","draft"].includes(bracket.tournament.status) ? <Button onClick={doJoinTournament}>Войти</Button> : null}
                  {token && myTeam && myTeamInTournament && ["open","registration","draft"].includes(bracket.tournament.status) ? <Button variant="secondary" onClick={doCheckIn}>{myTeamInTournament.checked_in ? "Uncheck" : "Check-in"}</Button> : null}
                  {isAdmin && ["open","registration","draft"].includes(bracket.tournament.status) ? <Button variant="secondary" onClick={doStartTournament}>Старт</Button> : null}
                  {isAdmin ? <Button variant="secondary" onClick={() => doDeleteTournament(bracket.tournament.id, true)}>Удалить</Button> : null}
                </div>
              </div>
            </Card>
            {bracket.tournament.rules_text ? <Card><div className="cardTitle">Правила / регламент</div><div className="prewrap" style={{ marginTop: 8 }}>{bracket.tournament.rules_text}</div></Card> : null}
            <Card>
              <div className="cardTitle">Участники</div>
              <div className="stack" style={{ marginTop: 10 }}>
                {(bracket.participants || []).map((p) => <div className="listItem" key={p.id}><b>{p.team?.name}</b> <span className="dot" /> <Pill tone={p.checked_in ? "green" : "neutral"}>{p.checked_in ? "checked-in" : "not checked-in"}</Pill></div>)}
                {!(bracket.participants || []).length ? <div className="muted">Пока никого нет.</div> : null}
              </div>
            </Card>
            <Card>
              <div className="row between"><div><div className="cardTitle">Сетка</div><div className="cardHint">Upper / lower / grand final.</div></div>{myTeam ? <Button variant="secondary" onClick={() => { const mine = Object.values(bracket.rounds || {}).flat().find((m) => [m.team1?.id, m.team2?.id].includes(myTeam.id) && !m.winner); if (mine) openMatch(mine.id); else setToast("Ваших матчей пока нет"); }}>Мой матч</Button> : null}</div>
              <div style={{ marginTop: 10 }}><BracketVisual bracket={bracket} myTeamId={myTeamId} onOpenMatch={openMatch} /></div>
            </Card>
          </>
        )}

        {screen === "match" && match && (
          <>
            <Card>
              <div className="cardTitle">{match.team1?.name || "TBD"} vs {match.team2?.name || "TBD"}</div>
              <div className="cardHint"><Pill tone={statusTone(match.status)}>{prettyStatus(match.status)}</Pill><span className="dot" /><Pill tone="blue">{groupLabel(match.bracket_group)}</Pill><span className="dot" />раунд: {match.round}</div>
            </Card>
            <Card>
              <div className="cardTitle">Репорты</div>
              <div className="stack" style={{ marginTop: 10 }}>
                {(match.reports || []).map((r) => <div className="listItem" key={r.id}><b>{r.reporter_team_id === match.team1?.id ? match.team1?.name : match.team2?.name}</b> <span className="dot" /> {r.score_team1}:{r.score_team2}</div>)}
                {!(match.reports || []).length ? <div className="muted">Пока никто не отправил результат.</div> : null}
              </div>
            </Card>
            {isAdmin ? <Card><div className="cardTitle">Админ-действия</div><div className="row" style={{ marginTop: 10 }}>{match.team1 ? <Button onClick={() => doResolveMatch(match.team1.id)}>Победитель: {match.team1.name}</Button> : null}{match.team2 ? <Button variant="secondary" onClick={() => doResolveMatch(match.team2.id)}>Победитель: {match.team2.name}</Button> : null}<Button variant="secondary" onClick={doDeleteMatch}>Удалить матч</Button></div></Card> : null}
            {token ? <Card>
              <div className="cardTitle">Ввести результат</div>
              {match.winner ? <div className="cardHint">Матч уже завершён.</div> : !myTeam ? <div className="cardHint">Сначала создай или найди команду.</div> : ![match.team1?.id, match.team2?.id].includes(myTeam.id) ? <div className="cardHint">Вы не участник этого матча.</div> : (
                <form className="form" onSubmit={doReportMatch}>
                  <label className="label">{match.team1?.name || "team1"}<input className="input" type="number" value={score1} onChange={(e) => setScore1(e.target.value)} /></label>
                  <label className="label">{match.team2?.name || "team2"}<input className="input" type="number" value={score2} onChange={(e) => setScore2(e.target.value)} /></label>
                  <label className="label">proof_url<input className="input" value={proofUrl} onChange={(e) => setProofUrl(e.target.value)} /></label>
                  <Button type="submit">Отправить</Button>
                </form>
              )}
            </Card> : null}
          </>
        )}

        {screen === "team" && (
          <>
            {!token ? <Card><div className="cardTitle">Нужно войти</div><div className="cardHint">Авторизуйся, чтобы создать команду.</div></Card> : myTeam ? (
              <>
                <Card>
                  <div className="cardTitle">{myTeam.name}</div>
                  <div className="cardHint"><Pill tone="green">роль: {myTeam.my_role || "player"}</Pill><span className="dot" /><span className="muted">invite code: <b>{myTeam.invite_code}</b></span></div>
                  <div className="row" style={{ marginTop: 10 }}><Button variant="secondary" onClick={doLeaveTeam}>Выйти</Button></div>
                </Card>
                <Card>
                  <div className="cardTitle">Состав / roster management</div>
                  <div className="stack" style={{ marginTop: 10 }}>
                    {(myTeam.members || []).map((m) => (
                      <div className="listItem row between" key={m.id}>
                        <div>
                          <b>{m.display_name || m.username || `user#${m.user_id}`}</b>
                          <div className="muted">{m.username ? `@${m.username}` : `id ${m.user_id}`} • {m.role}</div>
                          {m.steam_profile_url ? <div className="stack" style={{ gap: 8, marginTop: 8 }}>
                            <div className="row" style={{ alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                              {m.steam_avatar_url ? <img src={m.steam_avatar_url} alt="Steam avatar" style={{ width: 32, height: 32, borderRadius: 999, objectFit: "cover", border: "1px solid rgba(255,255,255,.12)" }} /> : null}
                              <div className="muted">{m.steam_display_name || m.steam_account_label || "Steam profile"}</div>
                            </div>
                            <div className="row" style={{ flexWrap: "wrap" }}>
                              <LinkButton href={m.steam_profile_url}>Открыть Steam</LinkButton>
                              <LinkButton href={m.dotabuff_url}>Dotabuff</LinkButton>
                              <LinkButton href={m.opendota_url}>OpenDota</LinkButton>
                            </div>
                          </div> : null}
                        </div>
                        {myTeam.my_role === "captain" && m.user_id !== me?.id ? (
                          <div className="row">
                            <Button variant="secondary" onClick={() => promoteMember(m.user_id)}>Сделать капитаном</Button>
                            <Button variant="secondary" onClick={() => kickMember(m.user_id)}>Кик</Button>
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </Card>
              </>
            ) : (
              <>
                <Card>
                  <div className="cardTitle">Создать команду</div>
                  <form className="form" onSubmit={doCreateTeam}>
                    <label className="label">Название команды<input className="input" value={teamName} onChange={(e) => setTeamName(e.target.value)} required /></label>
                    <Button type="submit">Создать</Button>
                  </form>
                </Card>
                <Card>
                  <div className="cardTitle">Вступить по invite code</div>
                  <form className="form" onSubmit={doJoinByCode}>
                    <label className="label">Код команды<input className="input" value={joinCode} onChange={(e) => setJoinCode(e.target.value)} placeholder="AB12CD34" /></label>
                    <Button type="submit" variant="secondary">Вступить</Button>
                  </form>
                </Card>
              </>
            )}
          </>
        )}

        {screen === "profile" && (
          <>
            <Card>
              <div className="row between top">
                <div>
                  <div className="cardTitle">Профиль игрока</div>
                  <div className="cardHint">{token ? <><Pill tone="green">вход выполнен</Pill><span className="dot" /><span className="muted">{me?.username}</span></> : <><Pill tone="orange">не авторизован</Pill></>}</div>
                </div>
                {token ? <Button variant="secondary" onClick={logout}>Выйти</Button> : null}
              </div>
              {!token ? (
                <>
                  {!tg?.initData ? <div className="form" style={{ marginTop: 12 }}>
                    <label className="label">Имя тестового пользователя<input className="input" value={devLoginName} onChange={(e) => setDevLoginName(e.target.value)} /></label>
                    <div className="row"><Button onClick={() => doDevLogin(devLoginName, false)}>Войти как тестовый пользователь</Button><Button variant="secondary" onClick={() => doDevLogin("testadmin", true)}>Войти как тестовый админ</Button></div>
                  </div> : <Button style={{ marginTop: 12 }} onClick={telegramAutoLogin}>Войти через Telegram</Button>}
                  <div className="twoCol" style={{ marginTop: 12 }}>
                    <form className="form" onSubmit={doRegister}><div className="cardTitle">Регистрация</div><label className="label">Логин<input className="input" value={regUsername} onChange={(e) => setRegUsername(e.target.value)} /></label><label className="label">Пароль<input className="input" type="password" value={regPassword} onChange={(e) => setRegPassword(e.target.value)} /></label><Button type="submit">Зарегистрироваться</Button></form>
                    <form className="form" onSubmit={doLogin}><div className="cardTitle">Вход</div><label className="label">Логин<input className="input" value={loginUsername} onChange={(e) => setLoginUsername(e.target.value)} /></label><label className="label">Пароль<input className="input" type="password" value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)} /></label><Button type="submit" variant="secondary">Войти</Button></form>
                  </div>
                </>
              ) : (
                <form className="form" onSubmit={saveProfile} style={{ marginTop: 12 }}>
                  <label className="label">Ник / display name<input className="input" value={profileDisplayName} onChange={(e) => setProfileDisplayName(e.target.value)} /></label>
                  <label className="label">Роль<input className="input" value={profileRole} onChange={(e) => setProfileRole(e.target.value)} placeholder="carry / mid / offlane / support" /></label>
                  <label className="label">Steam<input className="input" value={profileSteam} onChange={(e) => setProfileSteam(e.target.value)} placeholder="7656119... / mySteamName / https://steamcommunity.com/..." /></label>
                  <SteamSummary user={me} />
                  <label className="label">О себе<textarea className="input textarea" value={profileBio} onChange={(e) => setProfileBio(e.target.value)} /></label>
                  <Button type="submit">Сохранить профиль</Button>
                </form>
              )}
            </Card>
            {token ? <Card><div className="cardTitle">История матчей</div><div className="stack" style={{ marginTop: 10 }}>{history.map((h) => <div className="listItem" key={h.id}><b>{h.tournament_title}</b><div className="muted">{h.team1_name} vs {h.team2_name} • winner: {h.winner_name || "-"} • {groupLabel(h.bracket_group)}</div></div>)}{!history.length ? <div className="muted">Пока пусто.</div> : null}</div></Card> : null}
          </>
        )}

        {screen === "admin" && (
          !isAdmin ? <Card><div className="cardTitle">Доступ ограничен</div><div className="cardHint">Только для админа.</div></Card> : (
            <>
              <Card>
                <div className="cardTitle">Нормальная админ-панель</div>
                <div className="gridStats" style={{ marginTop: 10 }}>
                  <div className="stat"><div className="statNum">{adminOverview?.tournaments_count || 0}</div><div className="muted">турниров</div></div>
                  <div className="stat"><div className="statNum">{adminOverview?.running_tournaments || 0}</div><div className="muted">running</div></div>
                  <div className="stat"><div className="statNum">{adminOverview?.users_count || 0}</div><div className="muted">игроков</div></div>
                  <div className="stat"><div className="statNum">{adminOverview?.teams_count || 0}</div><div className="muted">команд</div></div>
                  <div className="stat"><div className="statNum">{adminOverview?.matches_count || 0}</div><div className="muted">матчей</div></div>
                </div>
              </Card>
              <Card>
                <div className="cardTitle">Создать турнир</div>
                <form className="form" onSubmit={doCreateTournament}>
                  <label className="label">Название<input className="input" value={tTitle} onChange={(e) => setTTitle(e.target.value)} required /></label>
                  <label className="label">Формат<select className="input" value={tFormat} onChange={(e) => setTFormat(e.target.value)}><option value="1v1">1v1</option><option value="5v5">5v5</option></select></label>
                  <label className="label">Сетка<select className="input" value={tBracketType} onChange={(e) => setTBracketType(e.target.value)}><option value="single">single elimination</option><option value="double">double elimination (beta, 4 teams)</option></select></label>
                  <label className="label">Макс. команд<input className="input" type="number" min="2" max="1024" value={tMaxTeams} onChange={(e) => setTMaxTeams(e.target.value)} /></label>
                  <label className="label">Старт<input className="input" type="datetime-local" value={tStartAt} onChange={(e) => setTStartAt(e.target.value)} /></label>
                  <label className="label">Правила / регламент<textarea className="input textarea" value={tRulesText} onChange={(e) => setTRulesText(e.target.value)} placeholder="Формат матчей, check-in, дедлайны, споры, штрафы..." /></label>
                  <Button type="submit">Создать турнир</Button>
                </form>
              </Card>
              <Card>
                <div className="cardTitle">Последние турниры</div>
                <div className="stack" style={{ marginTop: 10 }}>{(adminOverview?.recent_tournaments || []).map((t) => <div className="listItem row between" key={t.id}><div><b>{t.title}</b><div className="muted">{bracketLabel(t.bracket_type)} • {prettyStatus(t.status)}</div></div><div className="row"><Button variant="secondary" onClick={() => doDeleteTournament(t.id)}>Удалить</Button><Button onClick={() => openTournament(t.id)}>Открыть</Button></div></div>)}</div>
              </Card>
            </>
          )
        )}
      </main>

      <nav className="tabs">
        <button className={cx("tab", bottomTab === "tournaments" && "tab--active")} onClick={() => setScreen("tournaments")}>Турниры</button>
        <button className={cx("tab", bottomTab === "team" && "tab--active")} onClick={() => setScreen("team")}>Команда</button>
        <button className={cx("tab", bottomTab === "profile" && "tab--active")} onClick={() => setScreen("profile")}>Профиль</button>
        {isAdmin ? <button className={cx("tab", bottomTab === "admin" && "tab--active")} onClick={() => { refreshAdminOverview(); setScreen("admin"); }}>Админка</button> : null}
      </nav>

      <style>{css}</style>
    </div>
  );
}

const css = `
:root { color-scheme: dark; }
body { margin: 0; }
.app{ min-height:100vh; background:var(--bg); color:var(--text); padding:14px 14px 90px; box-sizing:border-box; font-family: ui-sans-serif, system-ui, Arial; }
.header{ display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:14px; }
.title{ font-size:28px; font-weight:900; }
.subtitle,.muted,.cardHint{ color:var(--muted); }
.stack{ display:grid; gap:14px; }
.card{ background:linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.04)); border:1px solid rgba(255,255,255,.08); border-radius:18px; padding:16px; box-shadow:0 8px 30px rgba(0,0,0,.18); }
.cardTitle,.sectionTitle{ font-size:18px; font-weight:800; }
.row{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
.between{ justify-content:space-between; }
.top{ align-items:flex-start; }
.actionsCol{ width:150px; }
.form{ display:grid; gap:12px; }
.label{ display:grid; gap:6px; font-size:14px; color:var(--muted); }
.input{ width:100%; box-sizing:border-box; border:1px solid rgba(255,255,255,.10); border-radius:14px; background:rgba(255,255,255,.06); color:var(--text); padding:12px 14px; outline:none; }
.textarea{ min-height:110px; resize:vertical; }
.btn{ border:0; border-radius:14px; padding:12px 16px; font-weight:800; cursor:pointer; }
.btn--primary{ background:var(--primary); color:var(--primaryText); }
.btn--secondary{ background:rgba(255,255,255,.08); color:var(--text); }
.btn:disabled{ opacity:.6; cursor:not-allowed; }
.msg{ background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.08); border-radius:14px; padding:12px 14px; }
.pill{ display:inline-flex; align-items:center; border-radius:999px; padding:4px 10px; font-size:12px; font-weight:800; border:1px solid rgba(255,255,255,.1); }
.pill--green{ background:rgba(52,199,89,.18); color:#a9ffbe; }
.pill--orange{ background:rgba(255,159,10,.18); color:#ffd49a; }
.pill--blue{ background:rgba(93,147,255,.18); color:#bdd2ff; }
.pill--purple{ background:rgba(174,102,255,.18); color:#dfc4ff; }
.pill--neutral{ background:rgba(255,255,255,.08); color:#fff; }
.dot{ display:inline-block; width:4px; height:4px; border-radius:50%; background:rgba(255,255,255,.25); margin:0 8px; }
.listItem{ border:1px solid rgba(255,255,255,.08); background:rgba(255,255,255,.04); border-radius:14px; padding:12px 14px; }
.bracketScroller{ overflow:auto; }
.bracketCols{ display:flex; gap:14px; min-width:max-content; }
.bracketCol{ width:220px; display:grid; gap:10px; }
.bracketColTitle{ font-size:14px; font-weight:800; color:var(--muted); margin-bottom:2px; }
.bracketMatch{ text-align:left; border:1px solid rgba(255,255,255,.1); background:rgba(255,255,255,.05); color:var(--text); border-radius:14px; padding:10px; display:grid; gap:6px; }
.bracketMatch--mine{ box-shadow:0 0 0 1px rgba(46,166,255,.7) inset; }
.bracketDivider{ height:1px; background:rgba(255,255,255,.08); }
.bracketMeta{ display:flex; justify-content:space-between; gap:8px; font-size:12px; color:var(--muted); }
.twoCol{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.gridStats{ display:grid; grid-template-columns:repeat(5,1fr); gap:10px; }
.stat{ padding:12px; border-radius:14px; background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.08); }
.statNum{ font-size:24px; font-weight:900; }
.prewrap{ white-space:pre-wrap; }
.tabs{ position:fixed; left:0; right:0; bottom:0; display:flex; gap:8px; padding:10px 14px calc(10px + env(safe-area-inset-bottom)); background:rgba(7,17,31,.92); backdrop-filter: blur(10px); border-top:1px solid rgba(255,255,255,.08); }
.tab{ flex:1; border:0; border-radius:14px; padding:14px 10px; background:rgba(255,255,255,.06); color:var(--text); font-weight:900; }
.tab--active{ background:rgba(255,255,255,.14); }
@media (max-width: 760px){ .twoCol{ grid-template-columns:1fr; } .gridStats{ grid-template-columns:repeat(2,1fr); } .actionsCol{ width:100%; } }
`;

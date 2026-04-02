import React, { useEffect, useMemo, useState } from "react";

const tg = window.Telegram?.WebApp ?? null;

const cx = (...a) => a.filter(Boolean).join(" ");

function useTelegramTheme() {
  const [theme, setTheme] = useState(() => tg?.themeParams || {});
  useEffect(() => {
    if (!tg) return;
    tg?.ready?.();
    tg?.expand?.();
    const handler = () => setTheme(tg.themeParams || {});
    tg.onEvent("themeChanged", handler);
    return () => tg.offEvent("themeChanged", handler);
  }, []);
  return theme;
}

function Pill({ children, tone = "neutral" }) {
  return <span className={cx("pill", `pill--${tone}`)}>{children}</span>;
}

function Card({ children }) {
  return <div className="card">{children}</div>;
}

function Button({ children, onClick, variant = "primary", full, type = "button", disabled }) {
  return (
    <button
      type={type}
      className={cx("btn", `btn--${variant}`, full && "btn--full")}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

function buildHeaders(token, json = false) {
  const h = {};
  if (json) h["Content-Type"] = "application/json";
  if (token) h.Authorization = `Bearer ${token}`;
  if (tg?.initData) h["X-Init-Data"] = tg.initData;
  return h;
}

async function apiGet(path, token) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    headers: buildHeaders(token),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
  return data;
}

async function apiPost(path, body, token) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: buildHeaders(token, true),
    body: JSON.stringify(body ?? {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
  return data;
}

function statusTone(status) {
  if (status === "finished") return "green";
  if (status === "ready") return "orange";
  if (status === "pending") return "neutral";
  if (status === "running") return "orange";
  if (status === "open" || status === "registration" || status === "draft") return "green";
  if (status === "disputed") return "orange";
  return "neutral";
}

function prettyStatus(status) {
  const map = {
    open: "open",
    registration: "registration",
    draft: "draft",
    running: "running",
    finished: "finished",
    pending: "pending",
    ready: "ready",
    disputed: "disputed",
  };
  return map[status] || status;
}

function roundTitle(round, roundsCount) {
  if (!roundsCount) return `Раунд ${round}`;
  if (round === roundsCount) return "Финал";
  if (round === roundsCount - 1) return "Полуфинал";
  if (round === roundsCount - 2) return "Четвертьфинал";
  return `Раунд ${round}`;
}

export default function App() {
  const theme = useTelegramTheme();

  const [screen, setScreen] = useState("tournaments");
  const [selectedTournamentId, setSelectedTournamentId] = useState(null);
  const [selectedMatchId, setSelectedMatchId] = useState(null);

  const [token, setToken] = useState(() => localStorage.getItem("token") || "");
  const [regUsername, setRegUsername] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [authMsg, setAuthMsg] = useState("");
  const [devLoginName, setDevLoginName] = useState("testuser");

  const [loading, setLoading] = useState(false);

  const [me, setMe] = useState(null);
  const isAdmin = !!me?.is_admin;

  const [tournaments, setTournaments] = useState([]);
  const [bracket, setBracket] = useState(null);
  const [match, setMatch] = useState(null);
  const [nextMatch, setNextMatch] = useState(null);

  const [myTeam, setMyTeam] = useState(null);
  const [teamName, setTeamName] = useState("");
  const [teamMsg, setTeamMsg] = useState("");

  const [tTitle, setTTitle] = useState("");
  const [tFormat, setTFormat] = useState("5v5");
  const [tMaxTeams, setTMaxTeams] = useState(8);
  const [tStartAt, setTStartAt] = useState("");

  const [score1, setScore1] = useState(0);
  const [score2, setScore2] = useState(0);
  const [proofUrl, setProofUrl] = useState("");
  const [matchMsg, setMatchMsg] = useState("");

  const styles = useMemo(() => {
    const bg = theme.bg_color || "#0b0f19";
    const text = theme.text_color || "#ffffff";
    const hint = theme.hint_color || "rgba(255,255,255,.65)";
    const link = theme.link_color || "#4da3ff";
    const button = theme.button_color || "#2ea6ff";
    const buttonText = theme.button_text_color || "#ffffff";
    const secondary = theme.secondary_bg_color || "rgba(255,255,255,.06)";
    return {
      "--bg": bg,
      "--text": text,
      "--hint": hint,
      "--link": link,
      "--btn": button,
      "--btnText": buttonText,
      "--card": secondary,
      "--border": "rgba(255,255,255,.10)",
    };
  }, [theme]);

  async function telegramAutoLogin() {
    if (!tg?.initData) return;
    if (token) return;
    setAuthMsg("");
    setLoading(true);
    try {
      const data = await apiPost("/auth/telegram", {}, null);
      localStorage.setItem("token", data.access_token);
      setToken(data.access_token);
      setAuthMsg("Вход через Telegram выполнен ✅");
    } catch (e) {
      setAuthMsg(`Не удалось войти через Telegram: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    telegramAutoLogin();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const list = await apiGet("/tournaments", token);
        if (alive) setTournaments(list);
      } catch (_) {}
    })();
    return () => {
      alive = false;
    };
  }, [token]);

  useEffect(() => {
    let alive = true;
    (async () => {
      if (!token) {
        setMe(null);
        return;
      }
      try {
        const profile = await apiGet("/me", token);
        if (alive) setMe(profile);
      } catch (_) {
        localStorage.removeItem("token");
        if (alive) {
          setToken("");
          setMe(null);
        }
      }
    })();
    return () => {
      alive = false;
    };
  }, [token]);

  useEffect(() => {
    let alive = true;
    (async () => {
      if (!token) {
        setMyTeam(null);
        return;
      }
      try {
        const team = await apiGet("/teams/me", token);
        if (alive) setMyTeam(team);
      } catch (_) {
        if (alive) setMyTeam(null);
      }
    })();
    return () => {
      alive = false;
    };
  }, [token]);

  async function refreshNextMatch() {
    if (!token) return;
    try {
      const m = await apiGet("/matches/next", token);
      setNextMatch(m);
    } catch (_) {
      setNextMatch(null);
    }
  }

  useEffect(() => {
    refreshNextMatch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, myTeam?.id]);

  async function refreshTournaments() {
    const list = await apiGet("/tournaments", token);
    setTournaments(list);
  }

  async function doRegister(e) {
    e?.preventDefault?.();
    setAuthMsg("");
    setLoading(true);
    try {
      const data = await apiPost("/auth/register", { username: regUsername, password: regPassword });
      localStorage.setItem("token", data.access_token);
      setToken(data.access_token);
      setAuthMsg("Регистрация успешна ✅");
      setRegPassword("");
    } catch (err) {
      setAuthMsg(`Ошибка регистрации: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function doLogin(e) {
    e?.preventDefault?.();
    setAuthMsg("");
    setLoading(true);
    try {
      const data = await apiPost("/auth/login", { username: loginUsername, password: loginPassword });
      localStorage.setItem("token", data.access_token);
      setToken(data.access_token);
      setAuthMsg("Вход выполнен ✅");
      setLoginPassword("");
    } catch (err) {
      setAuthMsg(`Ошибка входа: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function doDevLogin(username = "testuser", isAdminLogin = false) {
    setAuthMsg("");
    setLoading(true);
    try {
      const actualUsername = isAdminLogin ? (username || "testadmin") : (username || "testuser");
      const data = await apiPost("/auth/dev-login", { username: actualUsername, is_admin: isAdminLogin });
      localStorage.setItem("token", data.access_token);
      setToken(data.access_token);
      setAuthMsg(isAdminLogin ? "Тестовый админ-вход выполнен ✅" : "Тестовый вход выполнен ✅");
    } catch (err) {
      setAuthMsg(`Dev login недоступен: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem("token");
    setToken("");
    setMe(null);
    setMyTeam(null);
    setBracket(null);
    setMatch(null);
    setNextMatch(null);
    setAuthMsg("Вы вышли из аккаунта");
    setScreen("me");
  }

  function goTournaments() {
    setScreen("tournaments");
    setSelectedTournamentId(null);
    setSelectedMatchId(null);
    setBracket(null);
    setMatch(null);
    setMatchMsg("");
  }

  async function openTournament(tournamentId) {
    setSelectedTournamentId(tournamentId);
    setSelectedMatchId(null);
    setMatch(null);
    setMatchMsg("");
    setScreen("tournament");
    try {
      const b = await apiGet(`/tournaments/${tournamentId}/bracket`, token);
      setBracket(b);
    } catch (e) {
      setBracket(null);
      setAuthMsg(`Не удалось загрузить турнир: ${e.message}`);
    }
  }

  async function openMatch(matchId) {
    setSelectedMatchId(matchId);
    setScreen("match");
    setMatchMsg("");
    try {
      const m = await apiGet(`/matches/${matchId}`, token);
      setMatch(m);
      setScore1(0);
      setScore2(0);
      setProofUrl("");
    } catch (e) {
      setMatch(null);
      setMatchMsg(`Не удалось загрузить матч: ${e.message}`);
    }
  }

  function goBack() {
    if (screen === "match") {
      setScreen("tournament");
      setSelectedMatchId(null);
      setMatch(null);
      setMatchMsg("");
      return;
    }
    if (screen === "tournament" || screen === "create") {
      goTournaments();
    }
  }

  async function doCreateTournament(e) {
    e?.preventDefault?.();
    setAuthMsg("");
    setLoading(true);
    try {
      const payload = {
        title: tTitle,
        format: tFormat,
        max_teams: Number(tMaxTeams) || null,
        start_at: tStartAt ? new Date(tStartAt).toISOString() : null,
      };
      await apiPost("/tournaments", payload, token);
      setAuthMsg("Турнир создан ✅");
      setTTitle("");
      await refreshTournaments();
      goTournaments();
    } catch (err) {
      setAuthMsg(`Ошибка создания турнира: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function doCreateTeam(e) {
    e?.preventDefault?.();
    setTeamMsg("");
    setLoading(true);
    try {
      const team = await apiPost("/teams", { name: teamName }, token);
      setMyTeam(team);
      setTeamName("");
      setTeamMsg("Команда создана ✅");
      setScreen("tournaments");
      await refreshNextMatch();
    } catch (err) {
      setTeamMsg(`Ошибка: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  function isTeamInTournament(b) {
    if (!b || !myTeam) return false;
    return (b.participants || []).some((p) => p.team?.id === myTeam.id);
  }

  function myParticipantRecord(b) {
    if (!b || !myTeam) return null;
    return (b.participants || []).find((p) => p.team?.id === myTeam.id) || null;
  }

  const myParticipant = myParticipantRecord(bracket);
  const myCheckedIn = !!(myParticipant?.checked_in || myParticipant?.is_checked_in);

  async function doJoinTournament() {
    if (!selectedTournamentId || !myTeam) return;
    setAuthMsg("");
    setLoading(true);
    try {
      await apiPost(`/tournaments/${selectedTournamentId}/join`, { team_id: myTeam.id }, token);
      const b = await apiGet(`/tournaments/${selectedTournamentId}/bracket`, token);
      setBracket(b);
      setAuthMsg("Команда зарегистрирована ✅");
    } catch (err) {
      setAuthMsg(`Не удалось зарегистрироваться: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function doCheckIn() {
    if (!selectedTournamentId) return;
    setAuthMsg("");
    setLoading(true);
    try {
      await apiPost(`/tournaments/${selectedTournamentId}/check-in`, {}, token);
      const b = await apiGet(`/tournaments/${selectedTournamentId}/bracket`, token);
      setBracket(b);
      setAuthMsg("Check-in переключён ✅");
    } catch (err) {
      setAuthMsg(`Не удалось сделать check-in: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function doStartTournament() {
    if (!selectedTournamentId) return;
    setAuthMsg("");
    setLoading(true);
    try {
      await apiPost(`/tournaments/${selectedTournamentId}/start`, {}, token);
      const b = await apiGet(`/tournaments/${selectedTournamentId}/bracket`, token);
      setBracket(b);
      await refreshTournaments();
      setAuthMsg("Турнир запущен ✅");
    } catch (err) {
      setAuthMsg(`Не удалось запустить: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function doResolveMatch(winnerTeamId) {
    if (!match?.id || !winnerTeamId) return;

    setMatchMsg("");
    setLoading(true);
    try {
      await apiPost(`/matches/${match.id}/resolve`, { winner_team_id: winnerTeamId }, token);

      const refreshed = await apiGet(`/matches/${match.id}`, token);
      setMatch(refreshed);

      if (selectedTournamentId) {
        try {
          const b = await apiGet(`/tournaments/${selectedTournamentId}/bracket`, token);
          setBracket(b);
        } catch (_) {}
      }

      await refreshNextMatch();
      setMatchMsg("Матч вручную завершён ✅");
    } catch (err) {
      setMatchMsg(`Ошибка resolve: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  function myMatchInBracket(b) {
    if (!b || !myTeam) return null;
    const all = Object.values(b.rounds || {}).flat();
    return all.find((m) => m.team1?.id === myTeam.id || m.team2?.id === myTeam.id) || null;
  }

  async function doReportMatch(e) {
    e?.preventDefault?.();
    if (!match?.id) return;

    setMatchMsg("");
    setLoading(true);
    try {
      await apiPost(
        `/matches/${match.id}/report`,
        {
          score_team1: Number(score1) || 0,
          score_team2: Number(score2) || 0,
          proof_url: proofUrl || null,
        },
        token
      );

      const refreshed = await apiGet(`/matches/${match.id}`, token);
      setMatch(refreshed);

      if (selectedTournamentId) {
        try {
          const b = await apiGet(`/tournaments/${selectedTournamentId}/bracket`, token);
          setBracket(b);
        } catch (_) {}
      }
      await refreshNextMatch();

      if (refreshed?.status === "disputed") {
        setMatchMsg("Репорт отправлен ⚠️ Матч перешёл в спор.");
      } else {
        setMatchMsg("Результат отправлен ✅");
      }
    } catch (err) {
      setMatchMsg(`Ошибка: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  const headerTitle = (() => {
    if (screen === "tournaments") return "Турниры";
    if (screen === "tournament") return bracket?.tournament?.title || "Турнир";
    if (screen === "match") return "Матч";
    if (screen === "create") return "Создать турнир";
    if (screen === "team") return "Моя команда";
    if (screen === "me") return "Профиль";
    return "";
  })();

  const showBack = screen === "tournament" || screen === "match" || screen === "create";

  const bottomTab = (() => {
    if (screen === "team") return "team";
    if (screen === "me") return "me";
    return "tournaments";
  })();

  const roundsCount = useMemo(() => {
    const keys = Object.keys(bracket?.rounds || {});
    if (!keys.length) return 0;
    return Math.max(...keys.map((k) => Number(k) || 0));
  }, [bracket]);

  return (
    <div className="app" style={styles}>
      <header className="header">
        <div className="headerLeft">
          {showBack ? (
            <button className="backBtn" onClick={goBack}>
              ←
            </button>
          ) : null}
          <div>
            <div className="title">{headerTitle}</div>
            <div className="subtitle">Dota 2 • Mini App</div>
          </div>
        </div>
        <div className="headerRight">
          {isAdmin && screen === "tournaments" ? (
            <Button variant="secondary" onClick={() => setScreen("create")}>
              Создать
            </Button>
          ) : null}
        </div>
      </header>

      {!API_BASE && (
        <div className="warn">
          ⚠️ Не задан API адрес. Укажите <b>VITE_API_BASE</b> в webapp/.env
        </div>
      )}

      {authMsg && <div className="msg">{authMsg}</div>}

      <main className="content">
        {screen === "tournaments" && (
          <div className="stack">
            <Card>
              <div className="row row--top">
                <div className="grow">
                  <div className="cardTitle">Быстрые действия</div>
                  <div className="cardHint">
                    {myTeam ? (
                      <>
                        <Pill tone="green">команда: {myTeam.name}</Pill>
                        <span className="dot" />
                        <span className="muted">можно регаться в турниры</span>
                      </>
                    ) : token ? (
                      <>
                        <Pill tone="orange">нет команды</Pill>
                        <span className="dot" />
                        <span className="muted">создай команду, чтобы участвовать</span>
                      </>
                    ) : (
                      <>
                        <Pill tone="orange">не авторизован</Pill>
                        <span className="dot" />
                        <span className="muted">войдите, чтобы создать команду</span>
                      </>
                    )}
                  </div>
                </div>
                {!myTeam && token ? (
                  <Button variant="primary" onClick={() => setScreen("team")}>
                    Моя команда
                  </Button>
                ) : null}
              </div>
            </Card>

            <Card>
              <div className="row row--top">
                <div className="grow">
                  <div className="cardTitle">Мой следующий матч</div>
                  <div className="cardHint">
                    {nextMatch ? (
                      <>
                        <Pill tone={statusTone(nextMatch.status)}>{prettyStatus(nextMatch.status)}</Pill>
                        <span className="dot" />
                        <span className="muted">
                          {nextMatch.team1?.name || "TBD"} vs {nextMatch.team2?.name || "TBD"}
                        </span>
                      </>
                    ) : (
                      <>
                        <Pill tone="neutral">пока нет</Pill>
                        <span className="dot" />
                        <span className="muted">когда турнир запустят — тут появится матч</span>
                      </>
                    )}
                  </div>
                </div>
                <Button
                  variant={nextMatch ? "primary" : "secondary"}
                  onClick={() => {
                    if (!nextMatch) return;
                    setSelectedTournamentId(nextMatch.tournament_id);
                    openTournament(nextMatch.tournament_id).then(() => openMatch(nextMatch.id));
                  }}
                  disabled={!nextMatch}
                >
                  Открыть
                </Button>
              </div>
            </Card>

            <div className="row" style={{ justifyContent: "space-between" }}>
              <div className="cardTitle" style={{ margin: 0 }}>
                Список турниров
              </div>
              <Button variant="secondary" onClick={refreshTournaments} disabled={loading}>
                Обновить
              </Button>
            </div>

            {tournaments.length === 0 ? (
              <Card>
                <div className="cardTitle">Пока нет турниров</div>
                <div className="cardHint">Админ создаст турнир — он появится здесь.</div>
              </Card>
            ) : null}

            {tournaments.map((t) => (
              <Card key={t.id}>
                <div className="row row--top">
                  <div className="grow">
                    <div className="cardTitle">{t.title}</div>
                    <div className="cardHint">
                      <Pill tone={t.format === "1v1" ? "blue" : "purple"}>{t.format}</Pill>
                      <span className="dot" />
                      <Pill tone={statusTone(t.status)}>{prettyStatus(t.status)}</Pill>
                      {t.max_teams ? (
                        <>
                          <span className="dot" />
                          <span className="muted">макс. команд: {t.max_teams}</span>
                        </>
                      ) : null}
                    </div>
                  </div>
                  <Button variant="primary" onClick={() => openTournament(t.id)}>
                    Открыть
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}

        {screen === "tournament" && (
          <div className="stack">
            {!bracket ? (
              <Card>
                <div className="cardTitle">Загрузка…</div>
                <div className="cardHint">Если долго грузит — проверь API / доступ к серверу.</div>
              </Card>
            ) : (
              <>
                <Card>
                  <div className="row row--top">
                    <div className="grow">
                      <div className="cardTitle">Инфо</div>
                      <div className="cardHint">
                        <Pill tone={statusTone(bracket.tournament.status)}>{prettyStatus(bracket.tournament.status)}</Pill>
                        <span className="dot" />
                        <span className="muted">участников: {bracket.participants?.length || 0}</span>
                        {myTeam ? (
                          <>
                            <span className="dot" />
                            <span className="muted">ваша команда: {myTeam.name}</span>
                          </>
                        ) : null}
                        {isTeamInTournament(bracket) ? (
                          <>
                            <span className="dot" />
                            <Pill tone={myCheckedIn ? "green" : "orange"}>
                              {myCheckedIn ? "checked-in" : "not checked-in"}
                            </Pill>
                          </>
                        ) : null}
                      </div>
                    </div>

                    <div className="stack" style={{ gap: 8, width: 140 }}>
                      {token &&
                      myTeam &&
                      !isTeamInTournament(bracket) &&
                      (bracket.tournament.status === "open" ||
                        bracket.tournament.status === "registration" ||
                        bracket.tournament.status === "draft") ? (
                        <Button full variant="primary" onClick={doJoinTournament} disabled={loading}>
                          Войти
                        </Button>
                      ) : null}

                      {token &&
                      myTeam &&
                      isTeamInTournament(bracket) &&
                      (bracket.tournament.status === "open" ||
                        bracket.tournament.status === "registration" ||
                        bracket.tournament.status === "draft") ? (
                        <Button full variant="secondary" onClick={doCheckIn} disabled={loading}>
                          {myCheckedIn ? "Uncheck" : "Check-in"}
                        </Button>
                      ) : null}

                      {isAdmin &&
                      (bracket.tournament.status === "open" ||
                        bracket.tournament.status === "registration" ||
                        bracket.tournament.status === "draft") ? (
                        <Button
                          full
                          variant="secondary"
                          onClick={doStartTournament}
                          disabled={loading || (bracket.participants?.length || 0) < 2}
                        >
                          Старт
                        </Button>
                      ) : null}
                    </div>
                  </div>

                  {token && !myTeam ? (
                    <div className="msg" style={{ marginTop: 10 }}>
                      Чтобы участвовать — создай команду.
                      <div style={{ marginTop: 10 }}>
                        <Button variant="primary" onClick={() => setScreen("team")}>
                          Создать команду
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </Card>

                <Card>
                  <div className="cardTitle">Участники</div>
                  <div className="cardHint">Кто уже зарегистрировался.</div>
                  <div className="list" style={{ marginTop: 10 }}>
                    {(bracket.participants || []).length === 0 ? (
                      <div className="muted">Пока никого нет.</div>
                    ) : (
                      bracket.participants.map((p) => (
                        <div key={p.id} className="listItem">
                          <div className="row" style={{ justifyContent: "space-between" }}>
                            <span>
                              <span className="muted">•</span> <b>{p.team?.name}</b>
                            </span>
                            {"checked_in" in p || "is_checked_in" in p ? (
                              <Pill tone={p.checked_in || p.is_checked_in ? "green" : "orange"}>
                                {p.checked_in || p.is_checked_in ? "checked-in" : "not checked-in"}
                              </Pill>
                            ) : null}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </Card>

                <Card>
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <div>
                      <div className="cardTitle">Сетка</div>
                      <div className="cardHint">Карточки по раундам.</div>
                    </div>
                    {myTeam ? (
                      <Button
                        variant="secondary"
                        onClick={() => {
                          const mm = myMatchInBracket(bracket);
                          if (mm) openMatch(mm.id);
                          else setAuthMsg("Ваших матчей в этом турнире пока нет");
                        }}
                      >
                        Мой матч
                      </Button>
                    ) : null}
                  </div>

                  {Object.keys(bracket.rounds || {}).length === 0 ? (
                    <div className="muted" style={{ marginTop: 10 }}>
                      Сетка появится после старта турнира.
                    </div>
                  ) : (
                    <div className="stack" style={{ marginTop: 12 }}>
                      {Object.keys(bracket.rounds || {})
                        .map((k) => Number(k))
                        .sort((a, b) => a - b)
                        .map((r) => (
                          <div key={r} className="roundBlock">
                            <div className="roundTitle">{roundTitle(r, roundsCount)}</div>
                            <div className="stack" style={{ gap: 10, marginTop: 10 }}>
                              {bracket.rounds[r].map((m) => {
                                const t1 = m.team1?.name || "TBD";
                                const t2 = m.team2?.name || "TBD";
                                const isMine = myTeam && (m.team1?.id === myTeam.id || m.team2?.id === myTeam.id);
                                return (
                                  <div
                                    key={m.id}
                                    className={cx("matchCard", isMine && "matchCard--mine")}
                                    onClick={() => openMatch(m.id)}
                                    role="button"
                                    tabIndex={0}
                                  >
                                    <div className="row row--top">
                                      <div className="grow">
                                        <div className="matchTitle">
                                          {t1} <span className="muted">vs</span> {t2}
                                        </div>
                                        <div className="cardHint" style={{ marginTop: 6 }}>
                                          <Pill tone={statusTone(m.status)}>{prettyStatus(m.status)}</Pill>
                                          {isMine ? (
                                            <>
                                              <span className="dot" />
                                              <Pill tone="blue">ваш матч</Pill>
                                            </>
                                          ) : null}
                                          {m.winner ? (
                                            <>
                                              <span className="dot" />
                                              <span className="muted">
                                                победитель: <b>{m.winner.name}</b>
                                              </span>
                                            </>
                                          ) : null}
                                        </div>
                                      </div>
                                      <Button
                                        variant="secondary"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          openMatch(m.id);
                                        }}
                                      >
                                        Открыть
                                      </Button>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        ))}
                    </div>
                  )}
                </Card>
              </>
            )}
          </div>
        )}

        {screen === "match" && (
          <div className="stack">
            {!match ? (
              <Card>
                <div className="cardTitle">Загрузка…</div>
                <div className="cardHint">Если матч не открывается — возможно, он удалён.</div>
              </Card>
            ) : (
              <>
                <Card>
                  <div className="cardTitle">
                    {match.team1?.name || "TBD"} vs {match.team2?.name || "TBD"}
                  </div>
                  <div className="cardHint">
                    <Pill tone={statusTone(match.status)}>{prettyStatus(match.status)}</Pill>
                    <span className="dot" />
                    <span className="muted">
                      раунд: {match.round} • матч: {match.position}
                    </span>
                    {match.winner ? (
                      <>
                        <span className="dot" />
                        <span className="muted">
                          победитель: <b>{match.winner.name}</b>
                        </span>
                      </>
                    ) : null}
                  </div>
                </Card>

                <Card>
                  <div className="cardTitle">Репорты</div>
                  <div className="cardHint">Если репорты разные — матч уходит в спор.</div>

                  <div className="list" style={{ marginTop: 10 }}>
                    {(match.reports || []).length === 0 ? (
                      <div className="muted">Пока никто не отправил результат.</div>
                    ) : (
                      match.reports
                        .slice()
                        .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
                        .map((r) => {
                          const reporterName =
                            r.reporter_team_id === match.team1?.id
                              ? match.team1?.name
                              : r.reporter_team_id === match.team2?.id
                              ? match.team2?.name
                              : `team#${r.reporter_team_id}`;

                          return (
                            <div key={r.id} className="listItem">
                              <div className="row" style={{ justifyContent: "space-between" }}>
                                <span>
                                  <b>{reporterName}</b>
                                  <span className="muted"> отправил</span>
                                </span>
                                <Pill tone="neutral">
                                  {r.score_team1}:{r.score_team2}
                                </Pill>
                              </div>
                              {r.proof_url ? (
                                <div
                                  className="muted"
                                  style={{ marginTop: 6, fontSize: 12, wordBreak: "break-word" }}
                                >
                                  proof: {r.proof_url}
                                </div>
                              ) : null}
                            </div>
                          );
                        })
                    )}
                  </div>
                </Card>

                {isAdmin && match.status === "disputed" ? (
                  <Card>
                    <div className="cardTitle">Resolve спора</div>
                    <div className="cardHint">Админ может вручную выбрать победителя.</div>

                    <div className="row" style={{ marginTop: 10 }}>
                      {match.team1 ? (
                        <Button
                          variant="primary"
                          onClick={() => doResolveMatch(match.team1.id)}
                          disabled={loading}
                        >
                          Победитель: {match.team1.name}
                        </Button>
                      ) : null}

                      {match.team2 ? (
                        <Button
                          variant="secondary"
                          onClick={() => doResolveMatch(match.team2.id)}
                          disabled={loading}
                        >
                          Победитель: {match.team2.name}
                        </Button>
                      ) : null}
                    </div>
                  </Card>
                ) : null}

                {token ? (
                  <Card>
                    <div className="cardTitle">Ввести результат</div>
                    {!myTeam ? (
                      <div className="cardHint">Сначала создай команду.</div>
                    ) : match.winner ? (
                      <div className="cardHint">Матч уже завершён.</div>
                    ) : !(match.team1 && match.team2) ? (
                      <div className="cardHint">Матч ещё не готов.</div>
                    ) : !(myTeam.id === match.team1?.id || myTeam.id === match.team2?.id) ? (
                      <div className="cardHint">Вы не участвуете в этом матче.</div>
                    ) : (
                      <form className="form" onSubmit={doReportMatch}>
                        <label className="label">
                          {match.team1?.name} (team1)
                          <input
                            className="input"
                            type="number"
                            min="0"
                            max="100"
                            value={score1}
                            onChange={(e) => setScore1(e.target.value)}
                          />
                        </label>
                        <label className="label">
                          {match.team2?.name} (team2)
                          <input
                            className="input"
                            type="number"
                            min="0"
                            max="100"
                            value={score2}
                            onChange={(e) => setScore2(e.target.value)}
                          />
                        </label>
                        <label className="label">
                          proof_url (опционально)
                          <input
                            className="input"
                            placeholder="Ссылка на скрин/матч"
                            value={proofUrl}
                            onChange={(e) => setProofUrl(e.target.value)}
                          />
                        </label>
                        <Button full type="submit" disabled={loading}>
                          Отправить
                        </Button>
                        {matchMsg ? <div className="msg">{matchMsg}</div> : null}
                      </form>
                    )}
                  </Card>
                ) : (
                  <Card>
                    <div className="cardTitle">Войти</div>
                    <div className="cardHint">Нужно авторизоваться, чтобы отправить результат.</div>
                    {tg?.initData ? (
                      <div style={{ marginTop: 10 }}>
                        <Button variant="primary" onClick={telegramAutoLogin} disabled={loading}>
                          Войти через Telegram
                        </Button>
                      </div>
                    ) : null}
                  </Card>
                )}
              </>
            )}
          </div>
        )}

        {screen === "create" && (
          <div className="stack">
            {!isAdmin ? (
              <Card>
                <div className="cardTitle">Доступ ограничен</div>
                <div className="cardHint">Создавать турниры может только администратор.</div>
              </Card>
            ) : (
              <Card>
                <div className="cardTitle">Админка: создать турнир</div>
                <div className="cardHint">Турнир появится в списке сразу после создания.</div>

                <form className="form" onSubmit={doCreateTournament}>
                  <label className="label">
                    Название
                    <input
                      className="input"
                      placeholder="Например: Dota 2 5v5 Cup"
                      value={tTitle}
                      onChange={(e) => setTTitle(e.target.value)}
                      required
                    />
                  </label>

                  <label className="label">
                    Формат
                    <select className="input" value={tFormat} onChange={(e) => setTFormat(e.target.value)}>
                      <option value="1v1">1v1</option>
                      <option value="5v5">5v5</option>
                    </select>
                  </label>

                  <label className="label">
                    Макс. команд (опционально)
                    <input
                      className="input"
                      type="number"
                      min="2"
                      max="1024"
                      value={tMaxTeams}
                      onChange={(e) => setTMaxTeams(e.target.value)}
                    />
                  </label>

                  <label className="label">
                    Старт (опционально)
                    <input
                      className="input"
                      type="datetime-local"
                      value={tStartAt}
                      onChange={(e) => setTStartAt(e.target.value)}
                    />
                  </label>

                  <Button full type="submit" disabled={loading}>
                    Создать турнир
                  </Button>
                </form>
              </Card>
            )}
          </div>
        )}

        {screen === "team" && (
          <div className="stack">
            {!token ? (
              <Card>
                <div className="cardTitle">Нужно войти</div>
                <div className="cardHint">Авторизуйся, чтобы создать команду.</div>
                {tg?.initData ? (
                  <div style={{ marginTop: 10 }}>
                    <Button variant="primary" onClick={telegramAutoLogin} disabled={loading}>
                      Войти через Telegram
                    </Button>
                  </div>
                ) : null}
              </Card>
            ) : myTeam ? (
              <>
                <Card>
                  <div className="cardTitle">{myTeam.name}</div>
                  <div className="cardHint">
                    <Pill tone="green">капитан</Pill>
                    <span className="dot" />
                    <span className="muted">team_id: {myTeam.id}</span>
                  </div>
                </Card>

                <Card>
                  <div className="cardTitle">Быстрые действия</div>
                  <div className="cardHint">Перейти к следующему матчу или в список турниров.</div>
                  <div className="row" style={{ marginTop: 10 }}>
                    <Button variant="primary" onClick={() => setScreen("tournaments")}>
                      Турниры
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={!nextMatch}
                      onClick={() => {
                        if (!nextMatch) return;
                        openTournament(nextMatch.tournament_id).then(() => openMatch(nextMatch.id));
                      }}
                    >
                      След. матч
                    </Button>
                  </div>
                </Card>
              </>
            ) : (
              <Card>
                <div className="cardTitle">Создать команду</div>
                <div className="cardHint">Для участия в турнирах нужна команда.</div>

                <form className="form" onSubmit={doCreateTeam}>
                  <label className="label">
                    Название команды
                    <input
                      className="input"
                      placeholder="Например: Radiant Kings"
                      value={teamName}
                      onChange={(e) => setTeamName(e.target.value)}
                      required
                    />
                  </label>
                  <Button full type="submit" disabled={loading}>
                    Создать
                  </Button>
                  {teamMsg ? <div className="msg">{teamMsg}</div> : null}
                </form>
              </Card>
            )}
          </div>
        )}

        {screen === "me" && (
          <div className="stack">
            <Card>
              <div className="row">
                <div>
                  <div className="cardTitle">Профиль</div>
                  <div className="cardHint">
                    {token ? (
                      <>
                        <Pill tone="green">выполнен вход</Pill>
                        <span className="dot" />
                        <span className="muted">{me?.username || "user"}</span>
                        <span className="dot" />
                        <span className="muted">
                          is_admin: <b>{me?.is_admin ? "true" : "false"}</b>
                        </span>
                        <div className="cardHint" style={{ marginTop: 8 }}>
                          <span className="muted">
                            TG id: <b>{tg?.initDataUnsafe?.user?.id ?? "нет"}</b> • initData:{" "}
                            <b>{tg?.initData ? tg.initData.length : 0}</b>
                          </span>
                        </div>
                      </>
                    ) : (
                      <>
                        <Pill tone="orange">не авторизован</Pill>
                        <span className="dot" />
                        <span className="muted">открой Mini App в Telegram или войди вручную</span>
                      </>
                    )}
                  </div>
                </div>
                {token ? <Button variant="secondary" onClick={logout}>Выйти</Button> : null}
              </div>

              {!token && tg?.initData ? (
                <div style={{ marginTop: 12 }}>
                  <Button variant="primary" onClick={telegramAutoLogin} disabled={loading}>
                    Войти через Telegram
                  </Button>
                </div>
              ) : null}

              {!token && (
                <>
                  {!tg?.initData ? (
                    <div className="card" style={{ marginTop: 12 }}>
                      <div className="cardTitle">Быстрый вход для локальной проверки</div>
                      <div className="cardHint">Работает только если на backend включён DEV_AUTH_ENABLED=true.</div>
                      <div className="form" style={{ marginTop: 10 }}>
                        <label className="label">
                          Имя тестового пользователя
                          <input
                            className="input"
                            value={devLoginName}
                            onChange={(e) => setDevLoginName(e.target.value)}
                            placeholder="testuser"
                          />
                        </label>
                        <div className="row">
                          <Button
                            variant="primary"
                            onClick={() => doDevLogin(devLoginName || "testuser", false)}
                            disabled={loading}
                          >
                            Войти как тестовый пользователь
                          </Button>
                          <Button
                            variant="secondary"
                            onClick={() => doDevLogin("testadmin", true)}
                            disabled={loading}
                          >
                            Войти как тестовый админ
                          </Button>
                        </div>
                      </div>
                    </div>
                  ) : null}
                  {authMsg ? <div className="msg">{authMsg}</div> : null}
                  <div className="twoCol" style={{ marginTop: 12 }}>
                    <form className="form" onSubmit={doRegister}>
                      <div className="cardTitle" style={{ marginBottom: 2 }}>
                        Регистрация (dev)
                      </div>
                      <label className="label">
                        Логин
                        <input className="input" value={regUsername} onChange={(e) => setRegUsername(e.target.value)} />
                      </label>
                      <label className="label">
                        Пароль
                        <input
                          className="input"
                          type="password"
                          value={regPassword}
                          onChange={(e) => setRegPassword(e.target.value)}
                        />
                      </label>
                      <Button full type="submit" disabled={loading || !API_BASE}>
                        Зарегистрироваться
                      </Button>
                    </form>

                    <form className="form" onSubmit={doLogin}>
                      <div className="cardTitle" style={{ marginBottom: 2 }}>
                        Вход (dev)
                      </div>
                      <label className="label">
                        Логин
                        <input className="input" value={loginUsername} onChange={(e) => setLoginUsername(e.target.value)} />
                      </label>
                      <label className="label">
                        Пароль
                        <input
                          className="input"
                          type="password"
                          value={loginPassword}
                          onChange={(e) => setLoginPassword(e.target.value)}
                        />
                      </label>
                      <Button full type="submit" variant="secondary" disabled={loading || !API_BASE}>
                        Войти
                      </Button>
                    </form>
                  </div>
                </>
              )}
            </Card>

            <Card>
              <div className="cardTitle">Памятка</div>
              <div className="cardHint">
                Для MVP:
                <span className="dot" />
                Турниры создаёт только админ
                <span className="dot" />
                Команды создают пользователи
                <span className="dot" />
                Сетка single-elimination
                <span className="dot" />
                Спорные матчи решает админ
              </div>
            </Card>
          </div>
        )}
      </main>

      <nav className="tabs tabs--bottom">
        <button className={cx("tab", bottomTab === "tournaments" && "tab--active")} onClick={() => goTournaments()}>
          Турниры
        </button>
        <button className={cx("tab", bottomTab === "team" && "tab--active")} onClick={() => setScreen("team")}>
          Команда
        </button>
        <button className={cx("tab", bottomTab === "me" && "tab--active")} onClick={() => setScreen("me")}>
          Профиль
        </button>
      </nav>

      <style>{css}</style>
    </div>
  );
}

const css = `
:root { color-scheme: light dark; }

.app{
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  padding: 14px 14px 86px;
  box-sizing: border-box;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, "Apple Color Emoji","Segoe UI Emoji";
}

.warn{
  margin: 10px 0 14px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(255,159,67,.10);
  color: var(--text);
  font-size: 13px;
}

.msg{
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,.06);
  font-size: 13px;
  white-space: pre-wrap;
}

.header{
  display:flex;
  justify-content:space-between;
  align-items:flex-start;
  gap:12px;
  margin-bottom: 12px;
}

.headerLeft{
  display:flex;
  align-items:flex-start;
  gap:10px;
}

.backBtn{
  width: 34px;
  height: 34px;
  border-radius: 12px;
  background: rgba(255,255,255,.06);
  border: 1px solid var(--border);
  color: var(--text);
  font-weight: 900;
  cursor: pointer;
}

.title{ font-size: 22px; font-weight: 800; letter-spacing: -0.02em; }
.subtitle{ font-size: 13px; color: var(--hint); margin-top: 4px; }

.tabs{
  display:flex;
  gap:8px;
  background: rgba(255,255,255,.04);
  border: 1px solid var(--border);
  padding: 6px;
  border-radius: 14px;
}

.tabs--bottom{
  position: fixed;
  left: 14px;
  right: 14px;
  bottom: 14px;
  z-index: 20;
}

.tab{
  flex: 1;
  background: transparent;
  border: 0;
  color: var(--hint);
  padding: 10px 10px;
  border-radius: 12px;
  font-weight: 800;
  cursor: pointer;
}

.tab--active{ background: rgba(255,255,255,.08); color: var(--text); }

.stack{ display:flex; flex-direction:column; gap:12px; }

.card{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 14px;
  box-shadow: 0 6px 18px rgba(0,0,0,.12);
}

.row{ display:flex; align-items:center; justify-content:space-between; gap:12px; }
.row--top{ align-items:flex-start; }
.grow{ flex: 1; }

.cardTitle{ font-size: 15px; font-weight: 800; margin-bottom: 6px; }

.cardHint{
  font-size: 13px;
  color: var(--hint);
  display:flex;
  align-items:center;
  gap:8px;
  flex-wrap: wrap;
}

.muted{ color: var(--hint); }

.dot{
  width: 4px;
  height: 4px;
  background: var(--border);
  border-radius: 999px;
  display:inline-block;
}

.pill{
  font-size: 12px;
  font-weight: 800;
  padding: 4px 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,.06);
}

.pill--green{ background: rgba(46, 204, 113, .18); }
.pill--orange{ background: rgba(255, 159, 67, .18); }
.pill--blue{ background: rgba(52, 152, 219, .18); }
.pill--purple{ background: rgba(155, 89, 182, .18); }

.btn{
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 10px 12px;
  font-weight: 900;
  cursor: pointer;
}

.btn:disabled{
  opacity: .6;
  cursor: not-allowed;
}

.btn--primary{
  background: var(--btn);
  color: var(--btnText);
  border-color: rgba(0,0,0,.08);
}

.btn--secondary{
  background: rgba(255,255,255,.06);
  color: var(--text);
}

.btn--full{ width: 100%; }

.form{
  margin-top: 12px;
  display:flex;
  flex-direction:column;
  gap:10px;
}

.twoCol{
  margin-top: 12px;
  display:grid;
  grid-template-columns: 1fr;
  gap:12px;
  align-items:start;
}

@media (min-width: 520px){
  .twoCol{ grid-template-columns: 1fr 1fr; }
}

.label{
  display:flex;
  flex-direction:column;
  gap:6px;
  font-size: 12px;
  color: var(--hint);
  font-weight: 800;
}

.input{
  background: rgba(255,255,255,.06);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 11px 12px;
  border-radius: 12px;
  outline: none;
}

.input::placeholder{ color: rgba(255,255,255,.35); }

.listItem{
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: rgba(0,0,0,.08);
  margin-top: 8px;
}

.roundTitle{
  font-weight: 900;
  font-size: 14px;
  letter-spacing: -0.01em;
}

.matchCard{
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 12px;
  background: rgba(0,0,0,.10);
  cursor: pointer;
}

.matchCard--mine{
  border-color: rgba(46, 204, 113, .55);
  box-shadow: 0 0 0 2px rgba(46, 204, 113, .12) inset;
}

.matchTitle{
  font-weight: 900;
  font-size: 14px;
}
`;
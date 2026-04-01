# Что уже внедрено

Этот архив уже включает первую реальную доработку проекта:

## 1. Check-in перед стартом турнира
- капитан команды может нажать `Check-in` на странице турнира
- если перед стартом есть хотя бы одна checked-in команда, в сетку попадут только checked-in команды
- в списке участников видно статус `check-in / нет check-in`

## 2. Спор по результату матча
- если обе команды отправили одинаковый счёт, матч завершается автоматически
- если счёт разный, матч получает статус `спор`
- админ может вручную подтвердить победителя из карточки матча

## Что изменено
### backend
- `backend/app/routes/tournaments.py`
- `backend/app/routes/matches.py`
- `backend/app/schemas.py`
- `backend/app/main.py`
- `backend/app/models.py`

### webapp
- `webapp/src/App.jsx`

## Новые endpoints
- `POST /tournaments/{id}/check-in`
- `POST /matches/{id}/resolve`

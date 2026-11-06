# 푸어링아웃 매장노트 (pouring.html)

푸어링(본점)·메라키 두 매장을 위한 통합 매장 관리 앱. 사장 = 김승현(사용자 본인). 답변은 한국어로, 짧게.

## 현재 구조
- 파일 하나(pouring.html): 바닐라 JS + CSS, 빌드 없음.
- claude.ai 아티팩트로 게시 중: https://claude.ai/artifact/QsZnwxNWN2x81bsJBRcbca
- 저장·로그인·사진 업로드는 claude.ai 아티팩트 런타임(window.claude의 db / user / assets)으로 동작함. 브라우저에서 파일을 바로 열면 화면만 나오고 데이터는 비어 있음.
- db 컬렉션: monthnotes, schedule(doc id=날짜), dayoffs(날짜_직원키), todos, notices, checks, orders, docs, cleaning, cleanman, pins, extra, opencounts, closing.
- 아티팩트 안에서는 confirm()/prompt()가 막혀 있음. askConfirm / openSheet / alertBox를 쓸 것.

## 직원
- 순서 고정: 승현, 다슬, 준형, 정한, 원석, 우준, koha, 호정(장호정은 항상 맨 뒤).
- 근무표 대상은 WSTAFF(승현~우준). koha·호정은 shift:false.
- 풀네임: 김승현, 황다슬, 강준형, 최정한, 성원석, 최우준, 장호정.

## 탭
- 탭: 오늘 · TO DO · 근무표 · 자료실. 톱니바퀴 → 탭 이름·순서, 사람별 보기 권한.
- 근무표: 4주 달력(일~토). 하루 칸 왼쪽 = 메라키(8:00-10:30 승현, 10:30-19:30 2명), 오른쪽 = 본점(10:30-13:30 승현, 13:30-22:30 2명).
- 휴무 정원: 하루 1명, 수요일 3명(승현 제외). ★ = 희망휴무(선착순).
- 날짜 칸 편집은 사장만 할 수 있음. 직원은 희망휴무만 신청.

## 디자인 규칙(사용자 선호)
- 글씨: 굵은 글씨 금지, 모두 font-weight 400.
- 근무자 이름은 검정. 휴무·희망휴무 이름만 직원 색.
- 완료 체크에 줄긋기 없음.
- 입력은 작은 "+"만 둠. 빈칸 안내문구 없음. 바깥을 누르면 저장.
- 아이폰 메모장 느낌. 휴대폰 기준 600px 이하.

## 작업 방식
- 고친 뒤에는 무엇이 바뀌었는지 짧게 설명할 것.
- 직원들이 쓰는 앱에 반영하려면 아티팩트에 다시 게시해야 함(claude.ai 대화에서 게시).
- 나중 계획: 계정 없는 웹앱(GitHub Pages + Supabase)으로 이전. 직원별 비밀번호로 본인 줄만 수정 가능하게.

## Claude ↔ Codex 협업 (Claude가 진행 담당)
코드 변경 요청을 받으면 Claude가 아래 순서를 직접 실행한다. 질문·설명만 하는 요청에는 적용하지 않는다.

1. **구현**: Claude가 직접 수정한다. 시작 전에 `git status`로 작업 트리를 확인한다.
2. **Codex 검토(읽기 전용)**: 실제로 Codex를 호출한다.
   ```
   git diff HEAD > .codex-review/diff.patch   # 새 파일은 먼저 git add -N
   codex exec -s read-only --ephemeral -o .codex-review/result.md \
     "AGENTS.md와 CLAUDE.md를 따르는 읽기 전용 검토자로서 .codex-review/diff.patch의 변경을 검토해 줘. 요청 내용: <요청 요약>. 파일을 수정하지 마."
   ```
   - 읽기 전용 검토에는 항상 `codex exec -s read-only`를 쓴다. `codex review`에는 sandbox 옵션이 없어 읽기 전용이 보장되지 않는다. 또 `codex review --uncommitted`는 사용자 지시와 함께 쓸 수 없다(0.162.1에서 확인).
   - 지시 없이 기본 리뷰만 필요하면 `codex review --uncommitted`도 쓸 수 있다.
3. **수정**: Claude가 검토 결과를 판단해 반영한다. 근거가 약한 지적은 이유를 적고 넘어간다.
4. **테스트**: `node`로 `<script>` 문법을 검사하고(아래 참고), 필요하면 브라우저로 화면을 확인한다.
   ```
   node -e "const h=require('fs').readFileSync('pouring.html','utf8');[...h.matchAll(/<script>([\s\S]*?)<\/script>/g)].forEach(m=>new Function(m[1]));console.log('ok')"
   ```
- **반복 제한**: 검토 → 수정은 **최대 2회**. 2회가 지나도 남은 지적은 사용자에게 보고하고 끝낸다.
- **분담 구현**: 일을 나눌 때는 **파일 단위로만** 나눈다. Codex에게 맡길 때는 `codex exec -s workspace-write "<파일명>만 수정해 …"`로 맡긴다. 같은 파일을 두 도구가 동시에 수정하지 않는다. 지금은 앱이 pouring.html 하나라서 기본적으로 Claude가 구현한다.
- **커밋·push**: 이 앱 저장소는 GitHub에 올려도 된다(2026-11-04 사용자 허락, 웹앱 이전·배포용). 고친 내용을 게시할 때 커밋하고 이 앱의 GitHub 저장소로 push한다. 다른 저장소·서비스로는 올리지 않는다. 강제 push(--force)와 기록 지우기는 하지 않는다. 비밀키·토큰·카톡 대화 파일(`KakaoTalk_Chat_*`)은 절대 커밋하지 않는다. `.codex-review/`는 git에서 제외한다. Codex는 여전히 커밋·push하지 않는다(AGENTS.md).
- **보고**: 무엇을 바꿨는지, Codex 검토 결과(호출 성공 여부와 주요 지적), 반영 여부, 테스트 결과를 짧게 알린다.

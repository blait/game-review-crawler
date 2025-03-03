const puppeteerExtra = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');

puppeteerExtra.use(StealthPlugin());

async function crawlRecentPosts(monthsBack = 1, maxPages = 5) {
  let browser;
  try {
    console.log('크롤링 시작...');
    browser = await puppeteerExtra.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });

    const page = await browser.newPage();
    
    await page.setRequestInterception(true);
    page.on('request', (req) => {
      if (req.resourceType() === 'image' || req.resourceType() === 'stylesheet' || req.resourceType() === 'font') {
        req.abort();
      } else {
        req.continue();
      }
    });

    const baseUrl = 'https://gall.dcinside.com/board/lists/?id=wow_new3';
    const today = new Date('2025-02-24');
    const pastDate = new Date(today);
    pastDate.setMonth(today.getMonth() - monthsBack);
    console.log(`오늘: ${today}, ${monthsBack}개월 전: ${pastDate}`);

    const results = [];
    const postLinks = [];

    // 목록 크롤링
    for (let pageNum = 1; pageNum <= maxPages; pageNum++) {
      const url = `${baseUrl}&page=${pageNum}`;
      console.log(`페이지 ${pageNum} 크롤링 중...`);
      await page.goto(url, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(Math.floor(Math.random() * 1000) + 500);

      const posts = await page.evaluate(() => {
        const postElements = document.querySelectorAll('.gall_tit a:first-child');
        const dateElements = document.querySelectorAll('.gall_date');
        return Array.from(postElements).map((el, index) => {
          const rawDate = dateElements[index]?.title || dateElements[index]?.innerText || '날짜 없음';
          const formattedDate = rawDate.includes('/') ? `20${rawDate.replace(/\//g, '-')}` : rawDate;
          return {
            title: el.innerText,
            link: el.href,
            date: formattedDate
          };
        });
      });

      console.log('수집된 게시글:', posts);

      for (const post of posts) {
        const postDate = new Date(post.date);
        if (!isNaN(postDate) && postDate >= pastDate && post.link.startsWith('https://gall.dcinside.com')) {
          postLinks.push(post);
        }
      }
    }

    // 개별 게시글 크롤링 및 댓글 분리
    for (const post of postLinks) {
      await page.goto(post.link, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(Math.floor(Math.random() * 1000) + 500);

      const postData = await page.evaluate(() => {
        const title = document.querySelector('.title_subject')?.innerText || '제목 없음';
        const content = document.querySelector('.write_div')?.innerText.trim() || '본문 없음';
        const comments = Array.from(document.querySelectorAll('.comment_box .usertxt')).map(el => el.innerText.trim());
        return { title, content, comments };
      });

      // 댓글을 개별 레코드로 분리
      postData.comments.forEach(comment => {
        results.push({
          url: post.link,
          date: post.date,
          title: postData.title,
          content: postData.content,
          comment: comment
        });
      });

      // 댓글이 없는 경우 본문만 저장
      if (postData.comments.length === 0) {
        results.push({
          url: post.link,
          date: post.date,
          title: postData.title,
          content: postData.content,
          comment: null
        });
      }

      console.log(`게시글 크롤링 완료: ${post.title}`);
    }

    // JSON 파일로 저장
    const outputFile = `wow_reviews_${monthsBack}months.json`;
    fs.writeFileSync(outputFile, JSON.stringify(results, null, 2));
    console.log(`최근 ${monthsBack}개월 게시글 수: ${results.length}`);
    console.log(`결과가 ${outputFile}에 저장되었습니다.`);

    await browser.close();
  } catch (error) {
    console.error('에러:', error);
  } finally {
    if (browser) await browser.close();
  }
}

crawlRecentPosts(1, 3);
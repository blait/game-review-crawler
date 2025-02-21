const puppeteer = require('puppeteer-core');
const chromium = require('chrome-aws-lambda');

exports.handler = async (event) => {
  let browser;
  try {
    browser = await chromium.puppeteer.launch({
      args: chromium.args,
      defaultViewport: chromium.defaultViewport,
      executablePath: await chromium.executablePath,
      headless: true,
    });

    const page = await browser.newPage();
    const url = event.url;

    await page.goto(url, { waitUntil: 'networkidle2' });

    const data = await page.evaluate(() => {
      const titleElement = document.querySelector('.title_subject');
      const title = titleElement ? titleElement.innerText : '제목 없음';
      const commentElements = document.querySelectorAll('.comment_box .usertxt');
      const comments = Array.from(commentElements).map(el => el.innerText.trim());
      return { title, comments };
    });

    return {
      statusCode: 200,
      body: JSON.stringify({
        url,
        title: data.title,
        comments: data.comments
      }),
    };
  } catch (error) {
    console.error('에러 발생:', error);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: error.message }),
    };
  } finally {
    if (browser) {
      await browser.close();
    }
  }
};
#!/usr/bin/env node

const program = require('commander');
const fs = require('fs');
const inquirer = require('inquirer');
const json2csv = require('json2csv');
const moment = require('moment');
const path = require('path');
const properties = require('properties');
const puppeteer = require('puppeteer');
const { spawn } = require('child_process');
const yup = require('yup');

async function parse_args() {
  program
    .version('0.1.0')
    .option(
      '-t, --account-type [type]',
      'Account to download',
      /^(chequing|visa)$/
    )
    .option('-n, --account-name [name]', 'Account name to put for hledger')
    .option('-w, --watch', 'Watch the browser')
    .option('-f, --filename [filename]', 'The output filename')
    .option(
      '-s, --start [start]',
      'The start date to download from',
      /^\d{4}\/\d{2}\/\d{2}$/
    )
    .option('-a, --answers [file]', 'Answers to the questions')
    .parse(process.argv);

  let answers = {};
  try {
    answers = require(path.resolve(program.answers));
  } catch (e) {
    // ignore it
  }

  const result = {
    account_type: program.accountType || answers.account_type,
    account_name: program.accountName || answers.account_name,
    watch: program.watch || answers.watch || false,
    filename: program.filename || answers.filename,
    start: program.start || answers.start,
    lastpass_email: answers.lastpass_email,
    lastpass_website: answers.lastpass_website
  };

  const schema = yup.object().shape({
    account_type: yup
      .string()
      .required()
      .oneOf(['chequing', 'visa']),
    account_name: yup.string().required(),
    watch: yup.boolean(),
    filename: yup.string().required(),
    start: yup.string(),
    lastpass_email: yup.string(),
    lastpass_website: yup.string()
  });

  await schema.validate(result);

  return result;
}

function delay(ms) {
  return new Promise((resolve, reject) => setTimeout(resolve, ms));
}

function write_file(filename, data) {
  return new Promise((resolve, reject) => {
    fs.writeFile(filename, data, err => {
      if (err) {
        reject(err);
      } else {
        resolve();
      }
    });
  });
}

function wait_for_child_proc(proc) {
  return new Promise((resolve, reject) => {
    let stdout = '';
    if (proc.stdout) {
      proc.stdout.on('data', data => (stdout += data.toString()));
    }
    let stderr = '';
    if (proc.stderr) {
      proc.stderr.on('data', data => (stderr += data.toString()));
    }
    proc.on('close', code =>
      resolve({
        stdout: proc.stdout && stdout,
        stderr: proc.stderr && stderr,
        code
      })
    );
    proc.on('error', reject);
  });
}

async function login_lastpass(prefilled_email) {
  const { email } = prefilled_email
    ? { email: prefilled_email }
    : await inquirer.prompt([
        { type: 'input', name: 'email', message: 'LastPass email:' }
      ]);

  const proc = spawn('lpass', ['login', email], { stdio: 'inherit' });
  const { stdout, stderr, code } = await wait_for_child_proc(proc);
}

async function get_login_details_from_last_pass(prefiled_website) {
  const { website } = prefiled_website
    ? { website: prefiled_website }
    : await inquirer.prompt([
        { type: 'input', name: 'website', message: 'LastPass website:' }
      ]);

  const proc = spawn('lpass', ['show', website]);
  const { stdout } = await wait_for_child_proc(proc);
  const props = properties.parse('#' + stdout);

  return {
    username: props['Username'],
    password: props['Password'],
    url: props['URL']
  };
}

async function login_scotiabank(page, details) {
  await page.goto(details.url);
  await page.type("input[name='signon_form:userName']", details.username);
  await page.type("input[name='signon_form:password_0']", details.password);
  await page.click("input[name='signon_form:enter_sol']"); // click submit
}

async function answer_security_question(page) {
  await page.waitFor("input[name='mfaAuth_form:answer_0']");
  const question_text = await page.$eval(
    '.standard-table td:first-of-type',
    td => td.textContent
  );
  const { answer } = await inquirer.prompt([
    {
      type: 'input',
      name: 'answer',
      message: `Security Question: ${question_text}`
    }
  ]);
  await page.type("input[name='mfaAuth_form:answer_0']", answer); // type answer
  await page.click("input[id='mfaAuth_form:register:1']"); // click no
  await page.click("input[name='mfaAuth_form:j_id138']"); // click confirm
}

async function goto_chequing(page) {
  await page.waitFor('.account-type');
  await page.click('.account-type a');
}

async function extract_csv_rows_from_chequing(page, start_date) {
  await page.waitFor('.transTableTop');
  if (start_date) {
    await page.click("a[name='filter_form_SCO:j_id834']");
    await delay(2000);
    await page.type(
      "input[name='filter_form_SCO:transfer_date']",
      start_date.format('MM/DD/YYYY')
    );
    await page.click("input[name='filter_form_SCO:j_id855']");
    await delay(2000);
  }
  return await page.$$eval('.transTableTop tbody tr', rows => {
    return Array.from(rows)
      .filter(row => {
        return !(
          row.classList.contains('stmt') ||
          row.classList.contains('stmt-brk') ||
          row.classList.contains('stmt-currprd')
        );
      })
      .map(row => {
        // date is the first element
        const date = row.children[0].textContent.trim();

        // amount is the second element
        const [withdrawalNode, depositNode] = row.querySelectorAll('.number');
        const withdrawal = parseFloat(
          withdrawalNode.textContent.replace(',', '')
        );
        const deposit = parseFloat(depositNode.textContent.replace(',', ''));
        const amount = isNaN(withdrawal) ? deposit : -withdrawal;

        const description = row.children[1].innerText.trim();

        return {
          date,
          amount,
          description
        };
      });
  });
}

async function download_chequing_csv(page, options) {
  await goto_chequing(page);
  const extractedRows = await extract_csv_rows_from_chequing(
    page,
    options.start && moment(options.start, 'YYYY/MM/DD')
  );
  const csvRows = extractedRows.filter(row => row.amount !== 0).map(row => {
    const [description, company] = row.description.split('\n');
    return {
      date: moment(row.date, 'MMM. D, YYYY').format('YYYY/MM/DD'),
      amount: row.amount,
      account: options.account_name,
      description,
      company
    };
  });
  const csv = json2csv({
    data: csvRows,
    hasCSVColumnTitle: false,
    fields: ['date', 'amount', 'account', 'description', 'company']
  });
  await write_file(options.filename, csv);
}

async function goto_visa(page) {
  await page.waitFor('.account-type');
  const links = await page.$$('.account-type a');
  await links[1].click();
}

async function extract_csv_rows_from_visa(page, start_date) {
  await page.waitFor('.thtable');
  if (start_date) {
    await page.click("a[name='history_table_form:j_id732']");
    await delay(2000);
    await page.type(
      "input[name='history_table_form:transfer_date']",
      start_date.format('MM/DD/YYYY')
    );
    await page.click("input[name='history_table_form:j_id751']");
    await delay(2000);
  }
  return await page.$$eval('.thtable tr', rows => {
    return Array.from(rows)
      .filter(row => {
        return !(
          row.classList.contains('stmt') ||
          row.classList.contains('stmt-brk') ||
          row.classList.contains('stmt-currprd')
        );
      })
      .map(row => {
        // date is the first element
        const date = row.children[0].textContent.trim();

        // amount is the second element
        const [debitNode, creditNode] = row.querySelectorAll('.balance');
        const debit = parseFloat(debitNode.textContent.replace(',', ''));
        const credit = parseFloat(creditNode.textContent.replace(',', ''));
        const amount = isNaN(debit) ? credit : -debit;

        const description = row.children[2].innerText.trim();

        return {
          date,
          amount,
          description
        };
      });
  });
}

async function download_visa_csv(page, options) {
  await goto_visa(page);
  const extractedRows = await extract_csv_rows_from_visa(
    page,
    options.start && moment(options.start, 'YYYY/MM/DD')
  );
  const csvRows = extractedRows.filter(row => row.amount !== 0).map(row => {
    return {
      date: moment(row.date, 'MMM. D, YYYY').format('YYYY/MM/DD'),
      amount: row.amount,
      account: options.account_name,
      description: row.description,
      empty: ''
    };
  });
  const csv = json2csv({
    data: csvRows,
    hasCSVColumnTitle: false,
    fields: ['date', 'amount', 'account', 'empty', 'description']
  });
  await write_file(options.filename, csv);
}

async function run() {
  const options = await parse_args();

  await login_lastpass(options.lastpass_email);
  const details = await get_login_details_from_last_pass(
    options.lastpass_website
  );

  const browser = await puppeteer.launch({ headless: !options.watch });
  const page = await browser.newPage();

  await login_scotiabank(page, details);
  await answer_security_question(page);

  if (options.account_type === 'chequing') {
    await download_chequing_csv(page, options);
  } else if (options.account_type === 'visa') {
    await download_visa_csv(page, options);
  }

  await browser.close();

  console.log(`Downloaded ${options.filename} successfully!`);
}

run().catch(console.error);

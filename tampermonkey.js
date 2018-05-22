// ==UserScript==
// @name         ScotiaBank Visa Export CSV script
// @version      0.1
// @description  convert records in the same format as the chequing account
// @author       You
// @require      https://cdnjs.cloudflare.com/ajax/libs/babel-standalone/6.18.2/babel.js
// @require      https://cdnjs.cloudflare.com/ajax/libs/babel-polyfill/6.16.0/polyfill.js
// @require      https://cdnjs.cloudflare.com/ajax/libs/PapaParse/4.3.6/papaparse.min.js
// @require      https://cdnjs.cloudflare.com/ajax/libs/FileSaver.js/1.3.3/FileSaver.js
// @require      https://cdnjs.cloudflare.com/ajax/libs/date-fns/1.29.0/date_fns.js
// @match        https://www.scotiaonline.scotiabank.com/*
// ==/UserScript==

/* jshint ignore:start */
var inline_src = (<><![CDATA[
/* jshint ignore:end */
    /* jshint esnext: false */
    /* jshint esversion: 6 */

    // create a button
    const csvExportButton = document.createElement('button');
    csvExportButton.innerHTML = 'EXPORT CSV';
    csvExportButton.addEventListener('click', onClickExport);

    // insert the button
    const elementToInsertBefore = document.getElementById('history_table_form');
    elementToInsertBefore.parentNode.insertBefore(csvExportButton,elementToInsertBefore);

    // functions
    function onClickExport() {
        const elementRows = extractRows();
        saveAsCsv(elementRows.map(createCsvRow));
    }

    function extractRows() {
        const body = document.querySelector('.aa-module-transactions').querySelector('.thtable');
        const children = Array.from(body.children);
        return children.filter(node => !node.className.startsWith('stmt'));
    }

    function createCsvRow(node) {
        return {
            date: dateFns.format(dateFns.parse(node.children[0].textContent), 'M/D/YYYY'),
            amount: getAmount(node.children[3].textContent, node.children[4].textContent),
            nothing: '-',
            desc: '',
            desc2: node.children[2].textContent.trim()
        };
    }

    function getAmount(debit, credit) {
        if (debit) {
            return -parseFloat(debit.replace(/,/g,''));
        } else {
            return parseFloat(credit.replace(/,/g,''));
        }
    }

    function saveAsCsv(rows) {
        const string = Papa.unparse(rows, {
            header: false,
            quotes: [false, false, false, true, true],
        });
        const blob = new Blob([string], { type: 'text/csv;charset=utf-8' });
        saveAs(blob, 'pcbanking.csv', true);
    }

/* jshint ignore:start */
]]></>).toString();
var c = Babel.transform(inline_src, { presets: [ "es2015", "es2016" ] });
eval(c.code);
/* jshint ignore:end */

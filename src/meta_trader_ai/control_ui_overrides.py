from __future__ import annotations

from .control_extensions_impl import inject_forex_factory_control as _base_inject


_DAILY_REPORT_SCRIPT = r'''
<!-- AMIR branding and single-day historical report UX -->
<script>
(function(){
  function setupDailyReport(){
    const start=document.getElementById('btStartDate');
    const end=document.getElementById('btEndDate');
    const run=document.getElementById('runBt');
    if(!start||!end||!run)return false;

    const card=start.closest('.card');
    if(card){
      const title=card.querySelector('h2');
      if(title)title.textContent='Historical daily report';
      const description=Array.from(card.querySelectorAll('p.muted')).find(p=>p.id!=='historyStatus');
      if(description)description.textContent='Choose one trading day to generate its complete historical replay report. The report uses the same continuous engine with start date and end date set to the selected day.';
    }

    const startField=start.closest('.field');
    const endField=end.closest('.field');
    if(startField){
      const label=startField.querySelector('label');
      if(label&&!label.dataset.dailyReportLabel){
        label.textContent='Report date';
        label.dataset.dailyReportLabel='1';
      }
      startField.style.gridColumn='span 1';
    }
    if(endField){
      endField.style.display='none';
      endField.setAttribute('aria-hidden','true');
    }

    run.textContent='Generate daily report';

    const sync=()=>{if(start.value)end.value=start.value};
    if(!start.dataset.dailyReportBound){
      start.dataset.dailyReportBound='1';
      start.addEventListener('input',sync);
      start.addEventListener('change',sync);
      run.addEventListener('click',sync,true);
    }

    return true;
  }

  function preferLatestAvailableDate(){
    const start=document.getElementById('btStartDate');
    const end=document.getElementById('btEndDate');
    if(!start||!end||start.dataset.dailyDefaultReady==='1')return;
    if(end.value){
      start.value=end.value;
      end.value=start.value;
      start.dataset.dailyDefaultReady='1';
    }
  }

  setupDailyReport();
  [150,350,700,1200,2000].forEach(ms=>setTimeout(()=>{
    setupDailyReport();
    preferLatestAvailableDate();
  },ms));
})();
</script>
'''


def inject_forex_factory_control(html: str) -> str:
    """Apply the base control extensions plus AMIR branding and daily-report UX."""

    html = _base_inject(html)
    html = html.replace(
        '<div class="hero-eyebrow">META TRADER AI</div>',
        '<div class="hero-eyebrow">AMIR META TRADER AI</div>',
        1,
    )
    if '</body>' in html and 'single-day historical report UX' not in html:
        html = html.replace('</body>', _DAILY_REPORT_SCRIPT + '</body>', 1)
    return html

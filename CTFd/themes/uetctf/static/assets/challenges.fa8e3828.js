import{m as l,C as s,h as r,T as h,d,M as c}from"./index.69d1de7e.js";function o(e){let a=new DOMParser().parseFromString(e,"text/html");return a.querySelectorAll('a[href*="://"]').forEach(i=>{i.setAttribute("target","_blank")}),a.documentElement.outerHTML}window.Alpine=l;l.store("challenge",{data:{view:""}});l.data("Hint",()=>({id:null,html:null,async showHint(e){if(e.target.open){let a=(await s.pages.challenge.loadHint(this.id)).data;if(a.content)this.html=o(a.html);else if(await s.pages.challenge.displayUnlock(this.id)){let i=await s.pages.challenge.loadUnlock(this.id);if(i.success){let g=(await s.pages.challenge.loadHint(this.id)).data;this.html=o(g.html)}else e.target.open=!1,s._functions.challenge.displayUnlockError(i)}else e.target.open=!1}}}));l.data("Challenge",()=>({id:null,next_id:null,submission:"",tab:null,solves:[],response:null,async init(){r()},getStyles(){let e={"modal-dialog":!0};try{switch(s.config.themeSettings.challenge_window_size){case"sm":e["modal-sm"]=!0;break;case"lg":e["modal-lg"]=!0;break;case"xl":e["modal-xl"]=!0;break;default:break}}catch(t){console.log("Error processing challenge_window_size"),console.log(t)}return e},async init(){r()},async showChallenge(){new h(this.$el).show()},async showSolves(){this.solves=await s.pages.challenge.loadSolves(this.id),this.solves.forEach(e=>(e.date=d(e.date).format("MMMM Do, h:mm:ss A"),e)),new h(this.$el).show()},getNextId(){return l.store("challenge").data.next_id},async nextChallenge(){let e=c.getOrCreateInstance("[x-ref='challengeWindow']");e._element.addEventListener("hidden.bs.modal",t=>{l.nextTick(()=>{this.$dispatch("load-challenge",this.getNextId())})},{once:!0}),e.hide()},async submitChallenge(){this.response=await s.pages.challenge.submitChallenge(this.id,this.submission),await this.renderSubmissionResponse()},async renderSubmissionResponse(){this.response.data.status==="correct"&&(this.submission=""),this.$dispatch("load-challenges",this.current_page)}}));l.data("ChallengeBoard",()=>({loaded:!1,challenges:[],challenge:null,async init(){if(window.location.hash){let e=decodeURIComponent(window.location.hash.substring(1)),t=e.lastIndexOf("-");if(t>=0){let n=[e.slice(0,t),e.slice(t+1)][1];await this.loadChallenge(n)}}},getCategories(){const e=[];this.challenges.forEach(t=>{let{category:a}=t;a=a.split(".")[1],a&&!e.includes(a)&&(a===" "?e.unshift(a):e.push(a))});try{const t=s.config.themeSettings.challenge_category_order;if(t){const a=new Function(`return (${t})`);e.sort(a())}}catch(t){console.log("Error running challenge_category_order function"),console.log(t)}return e},getChallenges(e){let t=this.challenges;e!==null&&(t=this.challenges.filter(a=>a.category.split(".")[1]===e));try{const a=s.config.themeSettings.challenge_order;if(a){const n=new Function(`return (${a})`);t.sort(n())}}catch(a){console.log("Error running challenge_order function"),console.log(a)}return t},async loadChallenges(e){this.loaded=!1,this.challenges=await s.pages.challenges.getChallenges({q:e,field:"category"});for(let t of this.challenges)t.category===e&&(t.category=`${t.category}. `);this.loaded=!0},async loadChallenge(e){await s.pages.challenge.displayChallenge(e,t=>{t.data.view=o(t.data.view),l.store("challenge").data=t.data,l.nextTick(()=>{let a=c.getOrCreateInstance("[x-ref='challengeWindow']");a._element.addEventListener("hidden.bs.modal",n=>{history.replaceState(null,null," ")},{once:!0}),a.show(),history.replaceState(null,null,`#${t.data.name}-${e}`)})})}}));l.data("PageBoard",()=>({pages:[],async init(){await this.loadPages()},selectPage(e){this.current_page=`${e}`,this.$dispatch("load-challenges",this.current_page)},async loadPages(){const a=(await(await s.fetch("/api/v1/challenges/categories")).json()).data;this.pages=Array.from(new Set(a.map(n=>n.split(".")[0]))),this.current_page===null&&this.pages.length!=0&&this.selectPage(this.pages[0])}}));l.start();
